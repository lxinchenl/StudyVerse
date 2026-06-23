"""Course workflow agent — plan → per-module ReAct orchestration → dispatch experts → save path."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from app.agents.course_workflow_design import (
    MODULE_REACT_SYSTEM,
    PLAN_SYSTEM,
    RESOURCE_LABELS,
    TYPE_TO_EXPERT,
    build_module_react_prompt,
    build_plan_prompt,
    normalize_generate_task,
    parse_module_react_action,
    parse_plan,
)
from app.infrastructure.learning_path_store import new_course_id
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.services.app_services import PathService
from app.services.material_context import apply_document_read, material_basis_summary
from app.tools.executor import invoke_tool

WorkflowProgressFn = Callable[[dict[str, Any]], Awaitable[None]]

MAX_MODULE_REACT_STEPS = 10

_CONTEXT_LIST_KEYS = ("notes", "mindmaps", "exercise_sets", "code_lab_sets", "generated_resources")


class CourseWorkflowAgent(BaseAgent):
    name = "course-workflow-agent"
    role = "定制课程 Workflow Agent"
    skill_id = "course-workflow"

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryService,
        path_service: PathService,
        experts: dict[str, BaseAgent],
    ):
        self.llm = llm
        self.memory = memory
        self.path_service = path_service
        self._experts = experts

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        topic = str(context.get("course_topic") or context.get("topic") or context.get("message") or "").strip()
        course_id_ctx = str(context.get("course_id") or "db-principles").strip()
        if not topic:
            return {"error": "缺少课程主题 topic", "trace": self.trace("未提供学习主题")}

        confirmed = context.get("course_confirmed") is True or _user_confirmed(context.get("message", ""))
        proposal = context.get("course_proposal")
        if not confirmed and not context.get("force_course_run"):
            note = "请先向用户确认是否生成定制系统课，用户同意后再 call_skill course-workflow。"
            context["course_proposal"] = proposal
            return {"status": "needs_confirmation", "trace": self.trace(note), "note": note}

        async def progress(step: dict[str, Any]) -> None:
            entry = {
                "step": step.get("step"),
                "thought": step.get("thought", ""),
                "action": f"course:{step.get('action', '')}",
                "observation": step.get("observation", ""),
                "expert": self.name,
                "status": step.get("status", "done"),
            }
            steps = context.setdefault("react_steps", [])
            num = entry.get("step")
            replaced = False
            if num is not None:
                for i, existing in enumerate(steps):
                    if existing.get("step") == num and existing.get("expert") == self.name:
                        steps[i] = entry
                        replaced = True
                        break
            if not replaced:
                steps.append(entry)
            sink = context.get("event_sink")
            if sink is not None:
                from app.agents.chat_stream import pack_progress_event

                await sink(pack_progress_event(context))

        step_idx = 1
        await progress(
            {
                "step": step_idx,
                "action": "plan_course",
                "thought": "编排课程大纲",
                "observation": "执行中…",
                "status": "running",
            }
        )

        if isinstance(proposal, dict) and proposal.get("modules"):
            plan = proposal
        else:
            catalog_summary = await _load_catalog_summary(course_id_ctx)
            profile = context.get("profile") or self.memory.get_profile(user_id)
            conversation = self.memory.get_recent_conversation(user_id, limit=10)
            raw = await self.llm.complete(
                build_plan_prompt(
                    topic=topic,
                    profile=profile,
                    catalog_summary=catalog_summary,
                    conversation=conversation,
                ),
                system=PLAN_SYSTEM,
            )
            plan = parse_plan(raw)

        await progress(
            {
                "step": step_idx,
                "action": "plan_course",
                "thought": "课程大纲已就绪",
                "observation": f"《{plan['course_title']}》共 {len(plan['modules'])} 讲",
                "status": "done",
            }
        )

        profile = context.get("profile") or self.memory.get_profile(user_id)
        course_record: dict[str, Any] = {
            "id": new_course_id(),
            "title": plan["course_title"],
            "topic": topic,
            "summary": plan.get("summary") or f"围绕「{topic}」的系统学习课",
            "status": "in_progress",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "modules": plan["modules"],
        }

        for module in course_record["modules"]:
            step_idx, module_resources, react_plan = await _run_module_react(
                llm=self.llm,
                module=module,
                mod_context={**context, "message": f"{module['title']}：{module.get('objective', topic)}"},
                course_topic=topic,
                profile=profile,
                course_id_ctx=course_id_ctx,
                experts=self._experts,
                progress=progress,
                step_idx=step_idx,
                memory=self.memory,
            )
            module["resources"] = module_resources
            module["resource_plan"] = react_plan
            module["status"] = "done" if module_resources else "pending"

        step_idx += 1
        await progress(
            {
                "step": step_idx,
                "action": "save_path",
                "thought": "写入学习路径",
                "observation": "执行中…",
                "status": "running",
            }
        )
        saved = self.path_service.save_course(user_id, course_record)
        context["learning_course"] = saved
        context.setdefault("learning_courses", []).append(
            {
                "course_id": saved["id"],
                "title": saved["title"],
                "topic": saved["topic"],
                "summary": saved["summary"],
                "module_count": len(saved.get("modules") or []),
            }
        )
        context.setdefault("expert_outputs", []).append(
            f"已生成定制课《{saved['title']}》，共 {len(saved.get('modules') or [])} 讲，可在学习路径查看"
        )
        await progress(
            {
                "step": step_idx,
                "action": "save_path",
                "thought": "同步学习路径",
                "observation": f"课程 id={saved['id']}",
                "status": "done",
            }
        )

        summary = f"定制课《{saved['title']}》已就绪，进入学习路径即可按讲次学习"
        return {
            "course_id": saved["id"],
            "title": saved["title"],
            "modules": saved.get("modules") or [],
            "trace": self.trace(summary),
        }


async def _run_module_react(
    *,
    llm: LLMProvider,
    module: dict[str, Any],
    mod_context: dict[str, Any],
    course_topic: str,
    profile: dict[str, Any],
    course_id_ctx: str,
    experts: dict[str, BaseAgent],
    progress: Callable[[dict[str, Any]], Awaitable[None]],
    step_idx: int,
    memory: MemoryService,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    mod_title = module["title"]
    mod_context = dict(mod_context)
    mod_context.pop("retrieval", None)
    module["status"] = "in_progress"

    step_idx += 1
    await progress(
        {
            "step": step_idx,
            "action": "module_react",
            "thought": mod_title,
            "observation": "加载资料，开始自主编排…",
            "status": "running",
        }
    )
    await _ensure_module_material(
        mod_context, module, course_topic, mod_title, course_id_ctx, experts
    )
    material_summary = material_basis_summary(mod_context, memory)
    await progress(
        {
            "step": step_idx,
            "action": "module_react",
            "thought": mod_title,
            "observation": "资料就绪，逐轮规划资源顺序",
            "status": "done",
        }
    )

    observations: list[str] = []
    module_resources: list[dict[str, Any]] = []
    react_plan: list[dict[str, Any]] = []

    for _ in range(MAX_MODULE_REACT_STEPS):
        prompt = build_module_react_prompt(
            course_topic=course_topic,
            module=module,
            profile=profile,
            material_summary=material_summary,
            generated=module_resources,
            observations=observations,
        )
        raw = await llm.complete(prompt, system=MODULE_REACT_SYSTEM)
        action = parse_module_react_action(raw)
        if not action:
            raw = await llm.complete(prompt + "\n\n输出无效，请严格 JSON。", system=MODULE_REACT_SYSTEM)
            action = parse_module_react_action(raw)
        if not action:
            observations.append("JSON 无效，跳过本轮")
            continue

        action_name = str(action.get("action") or "").strip().lower()
        thought = str(action.get("thought") or "")[:200]

        if action_name == "finish_module":
            if not module_resources:
                observations.append("尚未生成资源，不能 finish_module")
                continue
            step_idx += 1
            order_desc = " → ".join(
                f"{r.get('order')}.{RESOURCE_LABELS.get(r.get('type'), r.get('type'))}"
                for r in module_resources
            )
            await progress(
                {
                    "step": step_idx,
                    "action": "finish_module",
                    "thought": thought or "本讲资源已够",
                    "observation": f"共 {len(module_resources)} 项，顺序：{order_desc}",
                    "status": "done",
                }
            )
            break

        task = normalize_generate_task(action)
        if not task:
            observations.append(f"无效 action: {action_name}")
            continue

        step_idx += 1
        label = RESOURCE_LABELS.get(task["type"], task["type"])
        order_num = len(module_resources) + 1
        reason = task.get("learning_order_reason") or thought
        await progress(
            {
                "step": step_idx,
                "action": "generate_resource",
                "thought": reason or task.get("title_hint", ""),
                "observation": f"第{order_num}项 · 调用 {label} Agent…",
                "status": "running",
            }
        )
        try:
            ref = await _dispatch_resource_task(mod_context, task, experts)
            if ref:
                ref["order"] = order_num
                ref["brief"] = task.get("brief", "")[:200]
                ref["learning_order_reason"] = task.get("learning_order_reason", "")
                module_resources.append(ref)
                react_plan.append({**task, "order": order_num, "resource_id": ref.get("resource_id")})
                obs = f"第{order_num}项 ✓ {ref['title']}"
            else:
                obs = "未产出资源"
        except Exception as exc:
            obs = f"失败：{exc}"
            module.setdefault("_warnings", []).append(f"{label}：{exc}")

        observations.append(f"generate_resource({task['type']}) → {obs}")
        await progress(
            {
                "step": step_idx,
                "action": "generate_resource",
                "thought": reason or task.get("title_hint", ""),
                "observation": obs,
                "status": "done",
            }
        )
    else:
        if not module_resources:
            module.setdefault("_warnings", []).append("编排轮次用尽，使用兜底资源")
            for task in _fallback_tasks(module, course_topic):
                ref = await _dispatch_resource_task(mod_context, task, experts)
                if ref:
                    order_num = len(module_resources) + 1
                    ref["order"] = order_num
                    module_resources.append(ref)
                    react_plan.append({**task, "order": order_num, "resource_id": ref.get("resource_id")})

    return step_idx, module_resources, react_plan


async def _ensure_module_material(
    mod_context: dict[str, Any],
    module: dict[str, Any],
    topic: str,
    mod_title: str,
    course_id: str,
    experts: dict[str, BaseAgent],
) -> None:
    chapter_key = str(module.get("chapter_key") or "").strip()
    if chapter_key:
        try:
            doc = await invoke_tool(
                "course-document-read",
                agent_context={**mod_context, "course_id": course_id},
                chapter_key=chapter_key,
            )
            if isinstance(doc, dict):
                apply_document_read(mod_context, doc)
        except Exception as exc:
            module.setdefault("_warnings", []).append(f"章节阅读失败：{exc}")

    if mod_context.get("retrieval", {}).get("chunks"):
        return
    retrieval_agent = experts.get("retrieval-agent")
    if retrieval_agent is None:
        return
    try:
        sub = {
            **mod_context,
            "plan": {
                "retrieval": {
                    "queries": (module.get("topics") or [topic, mod_title])[:4],
                    "entities": [],
                }
            },
        }
        await retrieval_agent.run(sub)
        if sub.get("retrieval"):
            mod_context["retrieval"] = sub["retrieval"]
    except Exception:
        pass


async def _dispatch_resource_task(
    mod_context: dict[str, Any],
    task: dict[str, Any],
    experts: dict[str, BaseAgent],
) -> dict[str, Any] | None:
    rtype = task["type"]
    expert_name = TYPE_TO_EXPERT.get(rtype)
    if not expert_name:
        return None
    expert = experts.get(expert_name)
    if expert is None:
        return None

    before = _resource_counts(mod_context)
    sub = {**mod_context}
    title_hint = str(task.get("title_hint") or "").strip()
    brief = str(task.get("brief") or "").strip()
    topic_kw = str(task.get("topic") or title_hint or brief[:40]).strip()
    if title_hint:
        sub["message"] = f"【{title_hint}】{brief}"
    else:
        sub["message"] = brief

    if rtype == "exercise":
        sub["exercise_mode"] = "generate"
        sub["exercise_topic"] = topic_kw
    elif rtype == "code_lab":
        sub["code_lab_mode"] = "generate"
        sub["code_lab_topic"] = topic_kw

    await expert.run(sub)
    _merge_expert_context(mod_context, sub)
    ref = _pick_new_resource(sub, rtype, before)
    if ref and title_hint and ref.get("title") == RESOURCE_LABELS.get(rtype):
        ref["title"] = title_hint
    return ref


def _resource_counts(ctx: dict[str, Any]) -> dict[str, int]:
    counts = {
        "note": len(ctx.get("notes") or []),
        "mindmap": len(ctx.get("mindmaps") or []),
        "exercise": len(ctx.get("exercise_sets") or []),
        "code_lab": len(ctx.get("code_lab_sets") or []),
        "video_script": sum(
            1 for r in (ctx.get("generated_resources") or []) if r.get("type") == "video_script"
        ),
    }
    return counts


def _merge_expert_context(target: dict[str, Any], source: dict[str, Any]) -> None:
    if source.get("retrieval"):
        target["retrieval"] = source["retrieval"]
    for key in _CONTEXT_LIST_KEYS:
        if source.get(key):
            target[key] = source[key]


def _pick_new_resource(
    ctx: dict[str, Any], rtype: str, before: dict[str, int]
) -> dict[str, Any] | None:
    if rtype == "note":
        rows = ctx.get("notes") or []
        if len(rows) > before["note"]:
            last = rows[-1]
            return {"type": "note", "resource_id": last.get("resource_id"), "title": last.get("title")}
    if rtype == "mindmap":
        rows = ctx.get("mindmaps") or []
        if len(rows) > before["mindmap"]:
            last = rows[-1]
            return {"type": "mindmap", "resource_id": last.get("resource_id"), "title": last.get("title")}
    if rtype == "exercise":
        rows = ctx.get("exercise_sets") or []
        if len(rows) > before["exercise"]:
            last = rows[-1]
            return {"type": "exercise", "resource_id": last.get("resource_id"), "title": last.get("title")}
    if rtype == "code_lab":
        rows = ctx.get("code_lab_sets") or []
        if len(rows) > before["code_lab"]:
            last = rows[-1]
            return {"type": "code_lab", "resource_id": last.get("resource_id"), "title": last.get("title")}
    if rtype == "video_script":
        videos = [r for r in (ctx.get("generated_resources") or []) if r.get("type") == "video_script"]
        if len(videos) > before["video_script"]:
            last = videos[-1]
            return {
                "type": "video_script",
                "resource_id": last.get("resource_id"),
                "title": last.get("title") or "讲解视频",
            }
    return None


def _fallback_tasks(module: dict[str, Any], topic: str) -> list[dict[str, Any]]:
    title = module.get("title") or topic
    objective = module.get("objective") or title
    return [
        {
            "type": "note",
            "title_hint": f"{title}笔记",
            "topic": topic,
            "brief": f"根据资料整理本讲笔记，目标：{objective}",
        },
        {
            "type": "exercise",
            "title_hint": f"{title}练习",
            "topic": title,
            "brief": f"生成 3~5 道题巩固：{objective}",
        },
    ]


async def _load_catalog_summary(course_id: str) -> str:
    try:
        result = await invoke_tool("course-catalog-list", agent_context={"course_id": course_id})
        lines = [str(result.get("summary") or "")]
        for ch in result.get("chapters") or []:
            lines.append(f"  {ch.get('chapter_key')}: {ch.get('chapter_title')}")
        return "\n".join(lines)[:3000]
    except Exception as exc:
        return f"目录加载失败：{exc}"


def _user_confirmed(message: str) -> bool:
    text = str(message or "").strip().lower()
    keys = ("同意", "好的", "可以", "开始", "生成", "需要", "是的", "行", "ok", "yes")
    return any(k in text for k in keys)


async def propose_course_plan(
    *,
    llm: LLMProvider,
    memory: MemoryService,
    user_id: str,
    topic: str,
    course_id: str,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog_summary = await _load_catalog_summary(course_id)
    prof = profile or memory.get_profile(user_id)
    conversation = memory.get_recent_conversation(user_id, limit=8)
    raw = await llm.complete(
        build_plan_prompt(
            topic=topic,
            profile=prof,
            catalog_summary=catalog_summary,
            conversation=conversation,
        ),
        system=PLAN_SYSTEM,
    )
    return parse_plan(raw)

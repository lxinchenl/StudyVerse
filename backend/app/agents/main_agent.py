import json
import re
from typing import Any

from app.agents.chat_stream import pack_progress_event
from app.agents.course_proposal_card import (
    build_proposal_card,
    normalize_client_proposal,
    proposal_card_reply,
)
from app.agents.registry import EXPERT_AGENTS, MAX_REACT_STEPS
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.infrastructure.profile_tools import format_profile_memory_digest
from app.services.material_context import (
    apply_document_read,
    ensure_material_basis,
    expert_requires_material,
    material_basis_summary,
    preload_material_context,
)

_PROFILE_TOOL_PARAMS = frozenset({"course", "goal", "recent_topics", "weak_points", "list_mode"})
_ME_TOOL_PARAMS = frozenset({"action", "updates", "remove_keys", "rewrite"})

_REACT_SYSTEM = """你是数据库课程学习助手的主 Agent，采用 ReAct：每轮先思考，再选一个 action，看到 Observation 后可继续下一轮。

可用 action：
1) reply — 直接回复用户（寒暄/无需查资料）
   {"thought":"...","action":"reply","reply":"..."}
2) call_expert — 调用一名专家（可多次、分多轮）
   {"thought":"...","action":"call_expert","expert":"retrieval-agent","retrieval":{"queries":["改写检索词"],"entities":["图谱实体"]}}
   调用 retrieval-agent 时必须给出 retrieval.queries（1~4条）和 retrieval.entities（0~5个）
   资源类专家：exercise-agent / note-agent / mindmap-agent / video-agent / code-lab-agent
   调用资源类专家前必须已有课程资料（本轮或短期记忆中的向量检索/文档阅读均可）；无资料时禁止调用
   获取课程资料两种方式（二选一或组合）：
   a) call_expert retrieval-agent — 适合点状概念、定义、公式等精细检索
      {"thought":"...","action":"call_expert","expert":"retrieval-agent","retrieval":{"queries":["..."],"entities":["..."]}}
   b) call_tool 文档阅读 — 适合「第 N 章」「整章」「某讲」等范围阅读
      先 call_tool course-catalog-list input:{} 查看章节目录与 material_id
      再 call_tool course-document-read input:{"chapter_key":"ch2"} 或 {"material_id":"..."}
   路由建议：章节/导图/本章总结 → catalog + document-read；单个知识点问答 → retrieval-agent
   思维导图/讲解视频/笔记/实操：有资料后 call_expert 对应专家；禁止跳过资料获取直接 call_skill
   练习题流程：
   - 先 call_expert exercise-agent exercise: {"mode":"search","topic":"..."}
   - needs_generate=true 时须先获取课程资料，再 exercise: {"mode":"generate","topic":"..."}
   call_expert exercise-agent 时必须带 exercise 字段：mode=search|generate，topic=知识点
   编程实操流程（类比练习题）：
   - 先 call_expert code-lab-agent code_lab: {"mode":"search","topic":"..."}
   - needs_generate=true 时须先获取课程资料，再 code_lab: {"mode":"generate","topic":"..."}
   call_expert code-lab-agent 时必须带 code_lab 字段：mode=search|generate，topic=知识点
   定制系统课 workflow（用户想系统学习/上课/要学习计划时）：
   a) 先 call_tool course-workflow-propose input:{"topic":"用户想学的主题"}
   b) 工具成功后系统会展示「课程大纲卡片」，由用户在卡片上确认/编辑/取消；你无需再用 reply 重复大纲或询问是否同意
   c) 禁止在 propose 后继续 call_expert 生成笔记/练习；禁止未经卡片确认 call_skill course-workflow
   d) 用户仅在卡片点击「同意」后，后端才会自动 call_skill course-workflow 执行完整 pipeline
   每讲具体生成哪些资源、以什么顺序生成，由 workflow 内讲次编排 Agent ReAct 自主决定
3) finish — 信息已够，生成最终回答（若已有课程资料则用资料作答）
   {"thought":"...","action":"finish"}
4) call_tool — 调用下方「可用工具 id」中的原子工具
   {"thought":"...","action":"call_tool","tool":"工具 id","input":{}}
   用户画像维护规则（必须执行）：
   - 当用户明确提供了“课程/目标/近期主题/薄弱点”等信息，且与当前画像不一致或画像为空时，优先调用 user-profile-update 更新画像
   - 可先调用 user-profile-gather 汇总记忆信号，再调用 user-profile-update 落盘
   - user-profile-update 的 input 可包含：
     {"course":"...","goal":"...","recent_topics":["..."],"weak_points":["..."],"list_mode":"merge|replace"}
   - 禁止仅在回答里口头复述，必须通过工具真正写入
   me 人设记忆维护规则（必须执行）：
   - 当用户明确声明长期偏好或者对你设置称呼时，调用 user-me-update 写入 me.json
   - 只写“长期稳定偏好”，不要把一次性任务内容写进 me
   - 建议：
     * 新增/覆盖：{"action":"add","updates":{"assistant_nickname":"贾维斯"}}
     * 删除字段：{"action":"delete","remove_keys":["assistant_nickname"]}
     * 整体重写：{"action":"rewrite","rewrite":{...}}
   - 参考长期记忆代理范式：显式声明才持久化，闲聊不写、临时指令不写
5) call_skill — 按 skill id 触发绑定 Agent 的完整 pipeline
   {"thought":"...","action":"call_skill","skill":"skill id","input":{}}

只输出一个 JSON 对象，不要其它文字。"""

_SUMMARIZE_SYSTEM = """你是数据库课程学习助手。必须严格依据「参考资料」回答，不得编造。
规则：
1. 只能使用参考资料中明确写出的内容
2. 若资料未提及，必须明确说「资料中未找到相关信息」
3. 禁止虚构页码、章节号、规范条文、评分标准
4. 回答时标注引用的资料编号，如【资料1】"""


async def _emit(context: dict[str, Any], event: dict[str, Any]) -> None:
    sink = context.get("event_sink")
    if sink is not None:
        await sink(event)


async def _emit_status(context: dict[str, Any], message: str) -> None:
    await _emit(context, {"type": "status", "message": message})


async def _emit_progress(context: dict[str, Any]) -> None:
    await _emit(context, pack_progress_event(context))


class MainAgent(BaseAgent):
    name = "main-agent"
    role = "主对话 Agent"

    def __init__(self, memory: MemoryService, llm: LLMProvider):
        self.memory = memory
        self.llm = llm

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("MainAgent 通过 react_loop 驱动，请调用 react_loop")

    async def react_loop(self, context: dict[str, Any], experts: dict[str, BaseAgent]) -> str:
        message = context["message"]
        profile = context.get("profile") or self.memory.get_profile(context["user_id"])
        context["profile"] = profile
        context["react_steps"] = []
        context["need_pipeline"] = False
        preload_material_context(context, self.memory)

        wf_action = str(context.get("course_workflow_action") or "").strip().lower()
        if wf_action == "confirm":
            proposal = normalize_client_proposal(
                context.get("course_proposal") if isinstance(context.get("course_proposal"), dict) else None,
                fallback_topic=str(context.get("message") or ""),
            )
            if not proposal.get("modules"):
                return "课程大纲无效，请重新说明学习目标后再编排。"
            topic = str(proposal.get("topic") or message or "").strip()
            context["course_proposal"] = proposal
            context["course_topic"] = topic
            context["course_confirmed"] = True
            context["course_proposal_card"] = build_proposal_card(proposal, topic, status="confirmed")
            await _emit_progress(context)
            return await self._run_course_workflow_skill(context, experts)

        if wf_action == "cancel":
            topic = str(context.get("message") or "")
            proposal = normalize_client_proposal(
                context.get("course_proposal") if isinstance(context.get("course_proposal"), dict) else None,
                fallback_topic=topic,
            )
            context["course_proposal_card"] = build_proposal_card(
                proposal or {"course_title": "定制系统课", "summary": "", "modules": []},
                topic,
                status="cancelled",
            )
            context["traces"].append(self.trace("用户取消定制系统课"))
            await _emit_progress(context)
            return "已取消定制系统课生成。如需重新编排，请说明学习目标。"

        for step_idx in range(1, MAX_REACT_STEPS + 1):
            await _emit_status(context, f"ReAct 第 {step_idx} 轮：主 Agent 思考中…")
            step = await self._react_step(context, step_idx, experts)
            if not step:
                break

            step.setdefault("status", "done")
            context["react_steps"].append(step)
            action = step.get("action", "")
            thought = step.get("thought", "")
            await _emit_progress(context)

            if action == "reply":
                reply = str(step.get("reply", "")).strip()
                if not reply:
                    reply = await self._direct_reply(message, profile, context.get("me", {}))
                context["traces"].append(
                    self.trace(f"[ReAct {step_idx}] {thought} → 直接回复")
                )
                await _emit_progress(context)
                return reply

            if action == "finish":
                context["traces"].append(
                    self.trace(f"[ReAct {step_idx}] {thought} → 生成最终回答")
                )
                await _emit_progress(context)
                delivery = self._resource_delivery_reply(context)
                if delivery:
                    return delivery
                reply = str(step.get("reply", "")).strip()
                if not context.get("retrieval", {}).get("chunks"):
                    if reply:
                        return reply
                    return await self._direct_reply(
                        message, context.get("profile", profile), context.get("me", {})
                    )
                await _emit_status(context, "正在根据检索资料生成最终回答…")
                return await self.summarize(context)

            if action == "call_expert":
                expert_name = str(step.get("expert", "")).strip()
                if expert_name not in experts:
                    step["observation"] = f"未知专家 {expert_name}"
                    context["traces"].append(
                        self.trace(f"[ReAct {step_idx}] {thought} → call_expert 失败: {step['observation']}")
                    )
                    await _emit_progress(context)
                    continue

                context["need_pipeline"] = True
                context["react_action"] = step
                self._apply_retrieval_action(context, step, message)
                self._apply_exercise_action(context, step, message)
                self._apply_code_lab_action(context, step, message)

                if expert_requires_material(expert_name, step):
                    ok, hint = ensure_material_basis(context, self.memory)
                    if not ok:
                        step["observation"] = hint
                        step["status"] = "done"
                        context["traces"].append(
                            self.trace(f"[ReAct {step_idx}] {thought} → {expert_name} 被拒绝: 无课程资料")
                        )
                        await _emit_progress(context)
                        continue
                    if hint:
                        step["observation"] = hint
                        await _emit_progress(context)

                step["status"] = "running"
                step["observation"] = f"正在调用 {expert_name}…"
                await _emit_progress(context)
                await _emit_status(context, f"正在执行 {EXPERT_AGENTS.get(expert_name, expert_name)}…")

                expert = experts[expert_name]
                result = await expert.run(context)
                observation = result.get("trace", {}).get("summary") or "专家执行完成"
                step["observation"] = observation
                step["status"] = "done"
                context["traces"].append(result["trace"])
                context["traces"].append(
                    self.trace(f"[ReAct {step_idx}] {thought} → {expert_name} | 观察: {observation[:160]}")
                )
                await _emit_progress(context)
                continue

            if action == "call_tool":
                tool_id = str(step.get("tool", "")).strip()
                tool_input = self._extract_tool_input(step, tool_id)
                step["status"] = "running"
                step["observation"] = f"正在调用工具 {tool_id}…"
                await _emit_progress(context)
                try:
                    manifest = self.get_tool_manifest(tool_id)
                    if manifest.get("expose_to_main") is False:
                        raise ValueError(f"工具 `{tool_id}` 仅供专家 Agent 内部使用")
                    result = await self.invoke_tool(tool_id, context=context, **tool_input)
                    if tool_id == "course-document-read" and isinstance(result, dict):
                        apply_document_read(context, result)
                        step["observation"] = str(result.get("summary") or "文档阅读完成")[:240]
                    elif tool_id == "course-catalog-list" and isinstance(result, dict):
                        step["observation"] = str(result.get("summary") or "目录加载完成")[:240]
                    elif tool_id == "user-profile-gather" and isinstance(result, dict):
                        context["profile_gather"] = result
                        step["observation"] = str(result.get("summary") or "画像记忆已整合")[:240]
                    elif tool_id == "user-profile-update" and isinstance(result, dict):
                        if result.get("profile"):
                            context["profile"] = {**context.get("profile", {}), **result["profile"]}
                        obs = str(result.get("summary") or "用户画像已更新")
                        if result.get("ok") and tool_input.get("recent_topics") is not None:
                            topics = result.get("profile", {}).get("recent_topics") or []
                            obs += f"；近期主题→{', '.join(topics[:6])}"
                        step["observation"] = obs[:320]
                    elif tool_id == "user-me-update" and isinstance(result, dict):
                        if isinstance(result.get("me"), dict):
                            context["me"] = result["me"]
                        step["observation"] = str(result.get("summary") or "已更新 me 人设记忆")[:320]
                    elif tool_id == "course-workflow-propose" and isinstance(result, dict):
                        if result.get("proposal"):
                            proposal = result["proposal"]
                            context["course_proposal"] = proposal
                            topic = str(tool_input.get("topic") or message or "").strip()
                            context["course_topic"] = topic
                            context["course_proposal_card"] = build_proposal_card(proposal, topic)
                        step["observation"] = "课程大纲 JSON 已生成，等待卡片确认"
                    else:
                        step["observation"] = f"工具 `{tool_id}` 执行成功: {str(result)[:240]}"
                    context["traces"].append(
                        self.trace(f"[ReAct {step_idx}] {thought} → call_tool({tool_id}) 成功")
                    )
                except Exception as exc:
                    step["observation"] = f"工具 `{tool_id}` 失败: {exc}"
                    context["traces"].append(
                        self.trace(f"[ReAct {step_idx}] {thought} → call_tool({tool_id}) 失败")
                    )
                step["status"] = "done"
                await _emit_progress(context)
                if tool_id == "course-workflow-propose" and context.get("course_proposal_card"):
                    context["traces"].append(
                        self.trace(f"[ReAct {step_idx}] {thought} → 课程大纲卡片待确认")
                    )
                    return proposal_card_reply(context["course_proposal_card"])
                continue

            if action == "call_skill":
                skill_id = str(step.get("skill", "")).strip()
                skill_input = step.get("input") if isinstance(step.get("input"), dict) else {}
                context.update(skill_input)
                if skill_id == "course-workflow":
                    if skill_input.get("course_topic"):
                        context["course_topic"] = skill_input["course_topic"]
                    if skill_input.get("course_confirmed"):
                        context["course_confirmed"] = True
                    if skill_input.get("course_proposal"):
                        context["course_proposal"] = skill_input["course_proposal"]
                context["need_pipeline"] = True
                step["status"] = "running"
                step["observation"] = f"正在执行 skill {skill_id}…"
                await _emit_progress(context)
                await _emit_status(context, f"正在执行 {skill_id}…")
                try:
                    result = await self.run_skill(skill_id, context, experts=experts)
                    observation = result.get("trace", {}).get("summary") or result.get("note") or "skill 执行完成"
                    step["observation"] = str(observation)[:240]
                    if trace := result.get("trace"):
                        context["traces"].append(trace)
                    context["traces"].append(
                        self.trace(f"[ReAct {step_idx}] {thought} → call_skill({skill_id})")
                    )
                except Exception as exc:
                    step["observation"] = f"skill `{skill_id}` 失败: {exc}"
                    context["traces"].append(
                        self.trace(f"[ReAct {step_idx}] {thought} → call_skill({skill_id}) 失败")
                    )
                step["status"] = "done"
                await _emit_progress(context)
                continue

            step["observation"] = f"未知 action: {action}"
            context["traces"].append(
                self.trace(f"[ReAct {step_idx}] 无效 action: {action}")
            )
            await _emit_progress(context)

        delivery = self._resource_delivery_reply(context)
        if delivery:
            context["traces"].append(self.trace("资源已生成，返回交付说明"))
            await _emit_progress(context)
            return delivery

        if context.get("retrieval", {}).get("chunks"):
            context["traces"].append(self.trace("达到 ReAct 步数上限，基于已有检索结果回答"))
            await _emit_status(context, "正在根据检索资料生成最终回答…")
            return await self.summarize(context)

        context["traces"].append(self.trace("达到 ReAct 步数上限，直接回复"))
        await _emit_progress(context)
        return await self._direct_reply(message, profile, context.get("me", {}))

    @staticmethod
    def _extract_tool_input(step: dict[str, Any], tool_id: str) -> dict[str, Any]:
        raw = step.get("input") if isinstance(step.get("input"), dict) else {}
        merged = dict(raw)
        if tool_id == "user-profile-update":
            for key in _PROFILE_TOOL_PARAMS:
                if key in step and key not in merged:
                    merged[key] = step[key]
        if tool_id == "user-me-update":
            for key in _ME_TOOL_PARAMS:
                if key in step and key not in merged:
                    merged[key] = step[key]
        return merged

    def _build_react_system(self, experts: dict[str, BaseAgent]) -> str:
        expert_list = " / ".join(experts.keys())
        tool_list = " / ".join(
            t["id"] for t in self.list_tools() if t.get("expose_to_main", True) is not False
        ) or "（无）"
        skill_list = " / ".join(
            s.get("id", "") for s in self.list_skills() if s.get("id")
        ) or "（无）"
        return (
            f"{_REACT_SYSTEM}\n\n"
            f"当前可用专家：{expert_list}\n"
            f"注册表专家说明：{'; '.join(f'{k}={v}' for k, v in EXPERT_AGENTS.items())}\n"
            f"可用工具 id：{tool_list}\n"
            f"可用 skill id：{skill_list}"
        )

    async def _react_step(
        self,
        context: dict[str, Any],
        step_idx: int,
        experts: dict[str, BaseAgent],
    ) -> dict[str, Any] | None:
        system = self._build_react_system(experts)
        prompt = self._build_react_prompt(context, step_idx)
        try:
            raw = await self.llm.complete(prompt, system=system)
            data = self._parse_json(raw)
            if isinstance(data, dict) and data.get("action"):
                data["step"] = step_idx
                return data
        except Exception:
            pass
        return None

    def _build_react_prompt(self, context: dict[str, Any], step_idx: int) -> str:
        profile = context.get("profile", {})
        message = str(context.get("message") or "")
        lines = [
            f"用户消息：{message}",
            f"当前课程：{profile.get('course', '') or '未设置'}",
            f"用户目标：{profile.get('goal', '') or '未知'}",
            f"近期主题：{', '.join(profile.get('recent_topics', [])) or '无'}",
            f"薄弱点：{', '.join(profile.get('weak_points', [])) or '未知'}",
            f"练习常错：{', '.join(profile.get('frequent_errors', [])) or '无'}",
            f"当前是第 {step_idx} 轮 ReAct。",
            material_basis_summary(context, self.memory),
        ]
        if context.get("profile_gather"):
            lines.append(
                format_profile_memory_digest(
                    user_id=context["user_id"],
                    course_id=str(context.get("course_id") or ""),
                    gather=context.get("profile_gather"),
                )
            )
        if context.get("course_proposal") and not context.get("course_confirmed"):
            title = str(context["course_proposal"].get("course_title") or "定制课")
            lines.append(
                f"\n已有待确认课程提案《{title}》，请引导用户在对话卡片上确认；不要自行 call_expert 或 call_skill"
            )
        steps = context.get("react_steps") or []
        if steps:
            lines.append("\n历史 Observation：")
            for prev in steps:
                lines.append(
                    f"- Step {prev.get('step')}: thought={prev.get('thought')} "
                    f"action={prev.get('action')} "
                    f"observation={prev.get('observation', '(无)')}"
                )
            search = context.get("exercise_search")
            if isinstance(search, dict) and search.get("matched_count") is not None:
                lines.append(
                    f"\n练习题查找摘要：matched={search.get('matched_count')} "
                    f"needs_generate={search.get('needs_generate')} "
                    f"unanswered={search.get('unanswered')} wrong={search.get('wrong')}"
                )
        lines.append("\n请输出本轮 JSON。")
        return "\n".join(lines)

    def _apply_retrieval_action(self, context: dict[str, Any], step: dict[str, Any], message: str) -> None:
        if step.get("expert") != "retrieval-agent":
            return
        block = step.get("retrieval") if isinstance(step.get("retrieval"), dict) else {}
        spec = {
            "queries": self._coerce_str_list(block.get("queries")),
            "entities": self._coerce_str_list(block.get("entities")),
        }
        if not spec["queries"]:
            spec["queries"] = self._fallback_retrieval_queries(message)
        if not spec["entities"]:
            spec["entities"] = self._fallback_retrieval_entities(message)
        spec["queries"] = spec["queries"][:4]
        spec["entities"] = spec["entities"][:5]
        step["retrieval"] = spec
        context["plan"] = {"retrieval": spec}

    def _apply_exercise_action(self, context: dict[str, Any], step: dict[str, Any], message: str) -> None:
        if step.get("expert") != "exercise-agent":
            return
        block = step.get("exercise") if isinstance(step.get("exercise"), dict) else {}
        mode = str(block.get("mode") or "search").strip().lower()
        if mode not in ("search", "generate"):
            mode = "search"
        topic = str(block.get("topic") or message).strip()[:120]
        step["exercise"] = {"mode": mode, "topic": topic}
        context["exercise_mode"] = mode
        context["exercise_topic"] = topic

    def _apply_code_lab_action(self, context: dict[str, Any], step: dict[str, Any], message: str) -> None:
        if step.get("expert") != "code-lab-agent":
            return
        block = step.get("code_lab") if isinstance(step.get("code_lab"), dict) else {}
        mode = str(block.get("mode") or "search").strip().lower()
        if mode not in ("search", "generate"):
            mode = "search"
        topic = str(block.get("topic") or message).strip()[:120]
        step["code_lab"] = {"mode": mode, "topic": topic}
        context["code_lab_mode"] = mode
        context["code_lab_topic"] = topic

    @staticmethod
    def _coerce_str_list(value: Any) -> list[str]:
        if value is None:
            return []
        items = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = " ".join(str(item).strip().split())
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    @staticmethod
    def _fallback_retrieval_queries(message: str) -> list[str]:
        base = " ".join(message.strip().split())
        if not base:
            return []
        queries = [base]
        cleaned = base.replace("？", "").replace("?", "").replace("吗", "").replace("呢", "")
        if cleaned != base:
            queries.append(cleaned)
        return MainAgent._coerce_str_list(queries)

    @staticmethod
    def _fallback_retrieval_entities(message: str) -> list[str]:
        parts = re.split(r"[，。；、？！,.;!?\s]+", message)
        entities = [p.strip() for p in parts if 2 <= len(p.strip()) <= 16]
        return MainAgent._coerce_str_list(entities)[:5]

    def _parse_json(self, raw: str) -> dict[str, Any] | None:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else None

    async def _run_course_workflow_skill(
        self,
        context: dict[str, Any],
        experts: dict[str, BaseAgent],
    ) -> str:
        context["need_pipeline"] = True
        step: dict[str, Any] = {
            "step": 1,
            "thought": "用户在卡片确认，启动定制课 workflow",
            "action": "call_skill",
            "skill": "course-workflow",
            "status": "running",
            "observation": "正在执行 course-workflow…",
        }
        context["react_steps"] = [step]
        await _emit_status(context, "正在生成定制系统课…")
        await _emit_progress(context)
        try:
            result = await self.run_skill("course-workflow", context, experts=experts)
            observation = result.get("trace", {}).get("summary") or result.get("note") or "skill 执行完成"
            step["observation"] = str(observation)[:240]
            step["status"] = "done"
            if trace := result.get("trace"):
                context["traces"].append(trace)
            context["traces"].append(self.trace("卡片确认 → course-workflow 完成"))
            await _emit_progress(context)
            delivery = self._resource_delivery_reply(context)
            if delivery:
                return delivery
            return str(observation)
        except Exception as exc:
            step["observation"] = f"course-workflow 失败: {exc}"
            step["status"] = "done"
            context["traces"].append(self.trace(f"course-workflow 失败: {exc}"))
            await _emit_progress(context)
            return f"定制课生成失败：{exc}"

    async def summarize(self, context: dict[str, Any]) -> str:
        retrieval = context.get("retrieval", {})
        chunks = retrieval.get("chunks", [])
        kg_lines = retrieval.get("kg_context", [])[:5]

        if not chunks:
            return (
                "我在当前课程资料中没有检索到与你问题直接相关的内容。"
                "请确认文档已放入 `data/courses/` 对应课程目录；若刚添加课件，"
                "可删除 `data/cache/course_material_chunks.json` 后重试。"
            )

        refs: list[str] = []
        for i, chunk in enumerate(chunks[:5], 1):
            text = (chunk.get("text") or "").strip()
            title = chunk.get("title") or chunk.get("chunk_id") or f"资料{i}"
            source = chunk.get("source") or ""
            refs.append(f"【资料{i}】《{title}》{f' ({source})' if source else ''}\n{text[:1800]}")

        kg_note = ""
        if kg_lines:
            kg_note = "知识图谱关系：\n" + "\n".join(
                f"- {r.get('source')} --{r.get('relation')}--> {r.get('target')}" for r in kg_lines
            )

        system = _SUMMARIZE_SYSTEM
        prompt = (
            f"参考资料：\n\n" + "\n\n".join(refs) + "\n\n"
            + (f"{kg_note}\n\n" if kg_note else "")
            + f"用户问题：{context['message']}\n\n"
            "请基于以上资料回答。若无相关内容，如实说明，不要猜测。"
        )
        return await self.llm.complete(prompt, system=system)

    async def _direct_reply(self, message: str, profile: dict[str, Any], me: dict[str, Any]) -> str:
        prompt = f"用户说：{message}\n用户画像：{profile.get('goal', '')}"
        return await self.llm.complete(prompt, system=str(me))

    @staticmethod
    def _resource_delivery_reply(context: dict[str, Any]) -> str | None:
        mindmaps = context.get("mindmaps") or []
        if mindmaps:
            title = str(mindmaps[-1].get("title") or "思维导图")
            return (
                f"已根据检索到的课程资料为您生成思维导图《{title}》，"
                f"请查看下方导图卡片；也可在「资源库」中再次打开。"
            )
        exercises = context.get("exercise_sets") or []
        if exercises:
            title = str(exercises[-1].get("title") or "练习题集")
            count = len(exercises[-1].get("questions") or [])
            suffix = f"共 {count} 道题" if count else ""
            return (
                f"已为您准备练习题《{title}》{('，' + suffix) if suffix else ''}，"
                f"请在下方面板作答，或前往练习页继续。"
            )
        notes = context.get("notes") or []
        if notes:
            title = str(notes[-1].get("title") or "学习笔记")
            return (
                f"已为您生成结构化笔记《{title}》，"
                f"请查看下方笔记内容；也可在「资源库」中再次打开。"
            )
        code_labs = context.get("code_lab_sets") or []
        if code_labs:
            title = str(code_labs[-1].get("title") or "编程练习")
            count = len(code_labs[-1].get("challenges") or [])
            return (
                f"已为您准备编程练习《{title}》"
                f"{('，共 ' + str(count) + ' 题') if count else ''}，"
                f"请在下方编写代码、运行并提交判题。"
            )
        for item in context.get("generated_resources") or []:
            if item.get("type") != "video_script":
                continue
            title = str(item.get("title") or "讲解视频")
            return f"已为您生成讲解动画《{title}》，请查看下方播放器。"
        courses = context.get("learning_courses") or []
        if courses:
            last = courses[-1]
            title = str(last.get("title") or "定制系统课")
            return (
                f"已为您生成定制系统课《{title}》，共 {last.get('module_count', 0)} 讲。"
                f"请前往「学习路径」查看并按讲次学习（含笔记、视频、练习等）。"
            )
        return None

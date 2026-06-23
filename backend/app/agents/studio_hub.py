"""LLM-driven MsgHub — production agents speak in turn, call retrieval/inquiry, then generate."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from uuid import uuid4

from app.agents.registry import EXPERT_AGENTS
from app.agents.studio_progress import make_studio_agent_sink
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.services.material_context import (
    apply_document_read,
    chunk_count,
    material_basis_summary,
)
from app.tools.executor import invoke_tool

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

MAX_TURNS_PER_AGENT = 12
MAX_GLOBAL_TURNS = 48

AGENT_TO_TYPE: dict[str, str] = {
    "exercise-agent": "exercise",
    "note-agent": "note",
    "mindmap-agent": "mindmap",
    "video-agent": "video_script",
    "code-lab-agent": "code_lab",
}

TYPE_LABELS: dict[str, str] = {
    "exercise": "练习题",
    "note": "笔记",
    "mindmap": "思维导图",
    "video_script": "讲解视频",
    "code_lab": "实操案例",
}

AGENT_SPECIALTY: dict[str, str] = {
    "exercise-agent": "根据课程资料出题、组卷，可调难度与题型",
    "note-agent": "ReAct 笔记：自动判断对话整理或课件笔记；课件模式自行提取资料+豆包识图，不依赖检索 Agent",
    "mindmap-agent": "生成 Mermaid 思维导图",
    "video-agent": "生成 HTML 讲解动画分镜与配音脚本",
    "code-lab-agent": "根据课程资料出 Python 编程题，沙箱 stdout 判题",
}

_HUB_RULES = """你在资源工作室 MsgHub 协作频道中，与其他专家按顺序轮流发言，直到你完成自己的资源生成后退出频道。

## 频道成员
- retrieval-agent：检索工具（不主动发言）。需要课程/课件类事实资料时优先 @ 他，不要自己编造。
- inquiry-desk：询问员。需要用户主观偏好（风格、侧重点、难度、题量、时长等）时 @ 她向用户确认。
- 其他专家：各自负责一种学习资源，按顺序发言协作。

## 获取课程资料的两种方式（call_retrieval）
需要课件、定义、公式、章节内容等**客观资料**时，必须优先 call_retrieval，查不到再基于已有信息谨慎推断并说明依据不足。

1) mode=search — 点状检索（概念、定义、公式、某个知识点）
   {"action":"call_retrieval","thought":"...","retrieval":{"mode":"search","queries":["检索词1"],"entities":["实体1"]}}
   queries 1~4 条，entities 0~5 个

2) mode=catalog — 查看课程章节目录（不确定章节键时先用这个）
   {"action":"call_retrieval","thought":"...","retrieval":{"mode":"catalog"}}

3) mode=document — 按章或文件整段阅读（「第 N 章」「整章」「某讲义」）
   {"action":"call_retrieval","thought":"...","retrieval":{"mode":"document","chapter_key":"ch2"}}
   或 {"retrieval":{"mode":"document","material_id":"..."}}
   已知 material_id 时可直接 document；否则先 catalog 再 document

## 询问用户（call_inquiry）
需要**用户主观信息**（要什么风格、突出什么、难度、题量、视频时长等）时：
{"action":"call_inquiry","thought":"...","inquiry":{"reason":"说明为何需要","questions":["问题1","问题2"]}}
questions 1~3 条，具体、可回答。

## 其他 action
- speak — 在频道发言、与同伴对齐（不触发工具）
  {"action":"speak","thought":"...","message":"频道里说的话"}
- generate — 资料与需求已够，开始生成你的资源，生成后你将退出频道
  {"action":"generate","thought":"...","message":"可选：告知大家你开始生成"}
- wait — 本轮暂无补充，把机会让给下一位
  {"action":"wait","thought":"..."}

## 原则
- 只输出一个 JSON 对象，不要 markdown 或其它文字
- message 用简体中文，简洁专业，像同事讨论
- 生成资源前尽量先拿到足够资料；资料不足可 call_retrieval 或 call_inquiry
- 完成 generate 后不要再发言（你将退出）
"""


def build_agent_system(agent_id: str) -> str:
    specialty = AGENT_SPECIALTY.get(agent_id, EXPERT_AGENTS.get(agent_id, agent_id))
    rtype = AGENT_TO_TYPE.get(agent_id, "")
    label = TYPE_LABELS.get(rtype, rtype or "资源")
    return (
        f"你是「{label}」专家（{agent_id}）。职责：{specialty}\n\n"
        f"{_HUB_RULES}\n\n"
        f"当前任务：为用户生成「{label}」。轮到你时输出 JSON。"
    )


def parse_hub_action(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and data.get("action") else None


@dataclass
class HubTranscriptLine:
    agent: str
    role: str
    content: str
    timestamp: str
    kind: str = "speak"


@dataclass
class AgentHubState:
    agent_id: str
    resource_type: str
    turns: int = 0
    observations: list[str] = field(default_factory=list)


class StudioHubSession:
    """Runs turn-based MsgHub until all producers generate or inquiry pauses."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        retrieval_agent: BaseAgent,
        experts: dict[str, BaseAgent],
        memory: MemoryService,
        agent_roles: dict[str, str],
        ts_fn: Callable[[], str],
    ):
        self.llm = llm
        self.retrieval_agent = retrieval_agent
        self.experts = experts
        self.memory = memory
        self.agent_roles = agent_roles
        self.ts_fn = ts_fn
        self.transcript: list[HubTranscriptLine] = []

    async def run(
        self,
        *,
        user_id: str,
        topic: str,
        types: list[str],
        context: dict[str, Any],
        producer_ids: list[str],
        agents: list[dict[str, Any]],
        emit: EventSink,
        hub: Callable[..., Awaitable[None]],
        set_agent: Callable[..., Awaitable[None]],
        persist_resource: Callable[..., Awaitable[dict[str, Any] | None]],
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Returns (completed, created_resources).
        completed=False means inquiry paused the session.
        """
        profile = context.get("profile") or self.memory.get_profile(user_id)
        context["profile"] = profile

        states: dict[str, AgentHubState] = {
            aid: AgentHubState(agent_id=aid, resource_type=AGENT_TO_TYPE.get(aid, ""))
            for aid in producer_ids
        }
        active: list[str] = list(producer_ids)
        created: list[dict[str, Any]] = []
        global_turns = 0

        if context.get("clarification_note"):
            await hub(
                emit,
                "user",
                context["clarification_note"],
                self.ts_fn(),
                kind="speak",
            )
            self._record("user", "你", context["clarification_note"], self.ts_fn())

        await hub(
            emit,
            "retrieval-agent",
            "我在线待命。需要课程资料时请 @我：点状检索（search）或按章阅读（catalog/document）。",
            self.ts_fn(),
            kind="system",
        )

        while active and global_turns < MAX_GLOBAL_TURNS:
            progressed = False
            for agent_id in list(active):
                if agent_id not in active:
                    continue
                state = states[agent_id]
                if state.turns >= MAX_TURNS_PER_AGENT:
                    resource = await self._force_generate(
                        agent_id=agent_id,
                        state=state,
                        context=context,
                        user_id=user_id,
                        topic=topic,
                        agents=agents,
                        emit=emit,
                        hub=hub,
                        set_agent=set_agent,
                        persist_resource=persist_resource,
                    )
                    if resource:
                        created.append(resource)
                    active.remove(agent_id)
                    progressed = True
                    continue

                global_turns += 1
                state.turns += 1
                await set_agent(agents, agent_id, "working", emit)

                action = await self._agent_turn(
                    agent_id=agent_id,
                    state=state,
                    context=context,
                    topic=topic,
                    types=types,
                    active=active,
                    producer_ids=producer_ids,
                )
                if not action:
                    await hub(
                        emit,
                        agent_id,
                        "（思考中遇到格式问题，我先听听大家的意见。）",
                        self.ts_fn(),
                    )
                    self._record(agent_id, self.agent_roles.get(agent_id, agent_id), "（格式问题，跳过本轮）", self.ts_fn())
                    await set_agent(agents, agent_id, "idle", emit)
                    continue

                action_name = str(action.get("action", "")).strip().lower()
                thought = str(action.get("thought") or "")[:200]
                if thought:
                    state.observations.append(f"[thought] {thought}")

                if action_name == "speak":
                    msg = str(action.get("message") or "").strip() or "…"
                    await hub(emit, agent_id, msg, self.ts_fn())
                    self._record(agent_id, self.agent_roles.get(agent_id, agent_id), msg, self.ts_fn())
                    await set_agent(agents, agent_id, "idle", emit)
                    progressed = True
                    continue

                if action_name == "wait":
                    await set_agent(agents, agent_id, "idle", emit)
                    progressed = True
                    continue

                if action_name == "call_retrieval":
                    obs = await self._call_retrieval(
                        action, context, agents, emit, hub, set_agent, requested_by=agent_id
                    )
                    state.observations.append(obs)
                    await set_agent(agents, agent_id, "idle", emit)
                    progressed = True
                    continue

                if action_name == "call_inquiry":
                    if context.get("user_clarification_provided"):
                        state.observations.append(
                            "用户已在本轮提供补充信息，请直接利用，无需再次 call_inquiry。"
                        )
                        await set_agent(agents, agent_id, "idle", emit)
                        progressed = True
                        continue
                    ok = await self._call_inquiry(
                        action,
                        context,
                        agent_id=agent_id,
                        agents=agents,
                        emit=emit,
                        hub=hub,
                        set_agent=set_agent,
                    )
                    if not ok:
                        return False, created
                    state.observations.append("询问员已向用户提问，等待用户补充。")
                    await set_agent(agents, agent_id, "waiting", emit)
                    progressed = True
                    continue

                if action_name == "generate":
                    msg = str(action.get("message") or "").strip()
                    if msg:
                        await hub(emit, agent_id, msg, self.ts_fn(), kind="action")
                        self._record(agent_id, self.agent_roles.get(agent_id, agent_id), msg, self.ts_fn())
                    resource = await self._generate_resource(
                        agent_id=agent_id,
                        state=state,
                        context=context,
                        user_id=user_id,
                        topic=topic,
                        agents=agents,
                        emit=emit,
                        hub=hub,
                        set_agent=set_agent,
                        persist_resource=persist_resource,
                    )
                    if resource:
                        created.append(resource)
                    await hub(
                        emit,
                        agent_id,
                        f"我的任务完成，退出频道。",
                        self.ts_fn(),
                        kind="system",
                    )
                    self._record(agent_id, self.agent_roles.get(agent_id, agent_id), "（已退出频道）", self.ts_fn())
                    active.remove(agent_id)
                    progressed = True
                    continue

                await set_agent(agents, agent_id, "idle", emit)

            if not progressed:
                break

        for agent_id in list(active):
            state = states[agent_id]
            resource = await self._force_generate(
                agent_id=agent_id,
                state=state,
                context=context,
                user_id=user_id,
                topic=topic,
                agents=agents,
                emit=emit,
                hub=hub,
                set_agent=set_agent,
                persist_resource=persist_resource,
            )
            if resource:
                created.append(resource)

        return True, created

    async def _agent_turn(
        self,
        *,
        agent_id: str,
        state: AgentHubState,
        context: dict[str, Any],
        topic: str,
        types: list[str],
        active: list[str],
        producer_ids: list[str],
    ) -> dict[str, Any] | None:
        system = build_agent_system(agent_id)
        prompt = self._build_prompt(
            agent_id=agent_id,
            state=state,
            context=context,
            topic=topic,
            types=types,
            active=active,
            producer_ids=producer_ids,
        )
        raw = await self.llm.complete(prompt, system=system)
        action = parse_hub_action(raw)
        if action:
            return action
        raw = await self.llm.complete(
            prompt + "\n\n上次输出无效，请严格输出一个 JSON 对象，含 action 字段。",
            system=system,
        )
        return parse_hub_action(raw)

    def _build_prompt(
        self,
        *,
        agent_id: str,
        state: AgentHubState,
        context: dict[str, Any],
        topic: str,
        types: list[str],
        active: list[str],
        producer_ids: list[str],
    ) -> str:
        profile = context.get("profile") or {}
        rtype = state.resource_type
        label = TYPE_LABELS.get(rtype, rtype)
        peers = [
            f"{aid}（{TYPE_LABELS.get(AGENT_TO_TYPE.get(aid, ''), '')}）"
            for aid in producer_ids
            if aid != agent_id
        ]
        lines = [
            f"用户主题：{topic}",
            f"本轮选择的资源类型：{', '.join(TYPE_LABELS.get(t, t) for t in types)}",
            f"你的产出：{label}",
            f"频道内仍在协作的专家：{', '.join(active)}",
            f"其他生产专家：{', '.join(peers) or '无'}",
            f"用户目标：{profile.get('goal') or '未知'}",
            f"薄弱点：{'、'.join(profile.get('weak_points') or []) or '未知'}",
            material_basis_summary(context, self.memory),
            f"这是你第 {state.turns} 次发言（上限 {MAX_TURNS_PER_AGENT}）。",
        ]
        if state.observations:
            lines.append("\n你本轮收到的 Observation：")
            for obs in state.observations[-8:]:
                lines.append(f"- {obs}")
        if self.transcript:
            lines.append("\n频道近期发言：")
            for row in self.transcript[-20:]:
                name = row.role if row.agent != "user" else "用户"
                lines.append(f"[{row.timestamp}] {name}: {row.content[:280]}")
        lines.append("\n请输出本轮 JSON action。")
        return "\n".join(lines)

    def _record(self, agent_id: str, role: str, content: str, timestamp: str, *, kind: str = "speak") -> None:
        self.transcript.append(
            HubTranscriptLine(agent=agent_id, role=role, content=content, timestamp=timestamp, kind=kind)
        )

    async def _call_retrieval(
        self,
        action: dict[str, Any],
        context: dict[str, Any],
        agents: list[dict[str, Any]],
        emit: EventSink,
        hub: Callable[..., Awaitable[None]],
        set_agent: Callable[..., Awaitable[None]],
        *,
        requested_by: str,
    ) -> str:
        block = action.get("retrieval") if isinstance(action.get("retrieval"), dict) else {}
        mode = str(block.get("mode") or "search").strip().lower()
        requester = self.agent_roles.get(requested_by, requested_by)
        await hub(
            emit,
            requested_by,
            f"@{self.agent_roles.get('retrieval-agent', '检索')} 请帮忙查一下资料。",
            self.ts_fn(),
            kind="action",
        )

        await set_agent(agents, "retrieval-agent", "working", emit)
        try:
            if mode == "catalog":
                result = await invoke_tool("course-catalog-list", agent_context=context)
                summary = str(result.get("summary") or "已获取课程目录。")
                detail = self._format_catalog(result)
                msg = f"{summary}\n{detail}"
                obs = f"目录查询：{summary}"
            elif mode == "document":
                kwargs: dict[str, Any] = {}
                if block.get("chapter_key"):
                    kwargs["chapter_key"] = str(block["chapter_key"])
                if block.get("material_id"):
                    kwargs["material_id"] = str(block["material_id"])
                if not kwargs:
                    msg = "请指定 chapter_key 或 material_id。可先 call_retrieval mode=catalog 查看目录。"
                    await hub(emit, "retrieval-agent", msg, self.ts_fn(), kind="error")
                    return msg
                result = await invoke_tool("course-document-read", agent_context=context, **kwargs)
                apply_document_read(context, result if isinstance(result, dict) else {})
                n = len((result or {}).get("chunks") or []) if isinstance(result, dict) else chunk_count(context)
                titles = []
                if isinstance(result, dict):
                    for ch in (result.get("chunks") or [])[:3]:
                        titles.append(ch.get("title") or ch.get("chunk_id") or "资料")
                title_hint = "、".join(titles) if titles else "文档"
                msg = f"阅读完成：新增 {n} 个文本块（{title_hint}），已同步频道。"
                obs = msg
            else:
                queries = _coerce_str_list(block.get("queries")) or [context.get("message", "")]
                entities = _coerce_str_list(block.get("entities"))
                queries = queries[:4]
                entities = entities[:5]
                result = await self.retrieval_agent.run(
                    {
                        **context,
                        "react_action": {
                            "retrieval": {"queries": queries, "entities": entities},
                        },
                    }
                )
                context.update(result)
                n_chunk = chunk_count(context)
                kg_n = len((context.get("retrieval") or {}).get("kg_context") or [])
                if n_chunk or kg_n:
                    msg = f"检索完成：{n_chunk} 条片段，知识图谱 {kg_n} 条。queries={';'.join(queries[:2])}"
                else:
                    msg = "检索完成：暂无精确命中，可换关键词或尝试按章阅读（mode=document）。"
                obs = msg

            await hub(emit, "retrieval-agent", msg, self.ts_fn(), kind="result")
            self._record("retrieval-agent", self.agent_roles.get("retrieval-agent", "检索"), msg, self.ts_fn(), kind="result")
            return f"{requester} 请求检索 → {obs}"
        except Exception as exc:
            err = f"检索失败：{exc}"
            await hub(emit, "retrieval-agent", err, self.ts_fn(), kind="error")
            return err
        finally:
            await set_agent(agents, "retrieval-agent", "idle", emit)

    async def _call_inquiry(
        self,
        action: dict[str, Any],
        context: dict[str, Any],
        *,
        agent_id: str,
        agents: list[dict[str, Any]],
        emit: EventSink,
        hub: Callable[..., Awaitable[None]],
        set_agent: Callable[..., Awaitable[None]],
    ) -> bool:
        block = action.get("inquiry") if isinstance(action.get("inquiry"), dict) else {}
        reason = str(block.get("reason") or "").strip() or f"{self.agent_roles.get(agent_id, agent_id)} 需要更多信息"
        questions = _coerce_str_list(block.get("questions"))
        if not questions:
            questions = ["请补充更具体的学习目标、风格或范围。"]
        questions = questions[:3]

        await emit({"type": "inquiry_walk"})
        await set_agent(agents, "inquiry-desk", "working", emit)
        desk_msg = f"受 {self.agent_roles.get(agent_id, agent_id)} 委托，需要向你确认：{reason}"
        await hub(emit, "inquiry-desk", desk_msg, self.ts_fn())
        self._record("inquiry-desk", self.agent_roles.get("inquiry-desk", "询问员"), desk_msg, self.ts_fn())
        await set_agent(agents, "inquiry-desk", "waiting", emit)
        await emit(
            {
                "type": "inquiry",
                "inquiry_id": f"inq-{uuid4().hex[:8]}",
                "reason": reason,
                "questions": questions,
                "requested_by": agent_id,
            }
        )
        await emit({"type": "hub_close"})
        await set_agent(agents, agent_id, "waiting", emit)
        return False

    async def _generate_resource(
        self,
        *,
        agent_id: str,
        state: AgentHubState,
        context: dict[str, Any],
        user_id: str,
        topic: str,
        agents: list[dict[str, Any]],
        emit: EventSink,
        hub: Callable[..., Awaitable[None]],
        set_agent: Callable[..., Awaitable[None]],
        persist_resource: Callable[..., Awaitable[dict[str, Any] | None]],
    ) -> dict[str, Any] | None:
        rtype = state.resource_type
        expert = self.experts.get(agent_id)
        if not expert:
            return None

        await set_agent(agents, agent_id, "working", emit)
        label = TYPE_LABELS.get(rtype, rtype)
        await hub(
            emit,
            agent_id,
            f"开始生成「{label}」…",
            self.ts_fn(),
            kind="action",
        )

        agent_context = {**context, "message": topic}
        agent_context["react_steps"] = []
        agent_context["event_sink"] = make_studio_agent_sink(
            agent_id=agent_id,
            emit=emit,
            hub=hub,
            ts_fn=self.ts_fn,
        )
        if agent_id == "exercise-agent":
            agent_context["exercise_mode"] = "generate"
            agent_context["exercise_topic"] = topic
        if agent_id == "code-lab-agent":
            agent_context["code_lab_mode"] = "generate"
            agent_context["code_lab_topic"] = topic

        try:
            result = await expert.run(agent_context)
            context.update(agent_context)
            resource = await persist_resource(user_id, rtype, topic, agent_context, result)
            if resource:
                await hub(
                    emit,
                    agent_id,
                    f"✓ {resource.get('title', label)} 已生成",
                    self.ts_fn(),
                    kind="result",
                )
                self._record(
                    agent_id,
                    self.agent_roles.get(agent_id, agent_id),
                    f"✓ {resource.get('title', label)} 已生成",
                    self.ts_fn(),
                    kind="result",
                )
                await emit(
                    {
                        "type": "resource_stored",
                        "agent_id": agent_id,
                        "resource": resource,
                    }
                )
            await set_agent(agents, agent_id, "done", emit)
            return resource
        except Exception as exc:
            await hub(emit, agent_id, f"生成失败：{exc}", self.ts_fn(), kind="error")
            await set_agent(agents, agent_id, "done", emit)
            return None

    async def _force_generate(
        self,
        *,
        agent_id: str,
        state: AgentHubState,
        context: dict[str, Any],
        user_id: str,
        topic: str,
        agents: list[dict[str, Any]],
        emit: EventSink,
        hub: Callable[..., Awaitable[None]],
        set_agent: Callable[..., Awaitable[None]],
        persist_resource: Callable[..., Awaitable[dict[str, Any] | None]],
    ) -> dict[str, Any] | None:
        await hub(
            emit,
            agent_id,
            "轮次即将用尽，我直接开始生成。",
            self.ts_fn(),
            kind="system",
        )
        return await self._generate_resource(
            agent_id=agent_id,
            state=state,
            context=context,
            user_id=user_id,
            topic=topic,
            agents=agents,
            emit=emit,
            hub=hub,
            set_agent=set_agent,
            persist_resource=persist_resource,
        )

    @staticmethod
    def _format_catalog(result: dict[str, Any]) -> str:
        lines: list[str] = []
        for ch in (result.get("chapters") or [])[:8]:
            key = ch.get("chapter_key", "")
            title = ch.get("chapter_title", key)
            n = ch.get("material_count", 0)
            lines.append(f"- {key} {title}（{n} 个文件）")
        return "\n".join(lines) if lines else ""


def _coerce_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []

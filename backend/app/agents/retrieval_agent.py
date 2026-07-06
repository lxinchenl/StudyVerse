from typing import Any

from app.interfaces.contracts import BaseAgent, Retriever
from app.services.material_context import merge_retrieval_search_result


class RetrievalAgent(BaseAgent):
    name = "retrieval-agent"
    role = "检索 Agent"

    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        react_action = context.get("react_action") or {}
        retrieval_block = react_action.get("retrieval") if isinstance(react_action.get("retrieval"), dict) else {}
        plan_block = (context.get("plan") or {}).get("retrieval") or {}
        queries = retrieval_block.get("queries") or plan_block.get("queries") or []
        entities = retrieval_block.get("entities") or plan_block.get("entities") or []

        result = await self.retriever.search(
            context["message"],
            queries=queries,
            entities=entities,
            top_k=5,
            course_id=context.get("course_id"),
            document_id=context.get("document_id"),
        )
        merge_retrieval_search_result(context, result)
        query_hint = "；".join(result.get("queries") or queries[:2])
        entity_hint = "、".join(result.get("entities") or entities[:3]) or "无"
        return {
            "retrieval": result,
            "trace": self.trace(
                f"检索 {len(result.get('chunks', []))} 条依据，图谱 {len(result.get('kg_context', []))} 条"
                f" | queries=[{query_hint}] entities=[{entity_hint}]"
            ),
        }

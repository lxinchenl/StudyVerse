import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.dependencies import build_orchestrator


async def main() -> None:
    orchestrator = build_orchestrator()
    result = await orchestrator.run(
        student_id="demo-student",
        message="我会 Python，但监督学习和神经网络公式容易混淆，希望通过图解、练习和代码案例学习。",
        target_topic="监督学习与神经网络入门",
    )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())


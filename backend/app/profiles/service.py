from app.domain.models import ProfileDimension, StudentProfile
from app.interfaces.contracts import ProfileExtractor


class InMemoryProfileRepository:
    def __init__(self):
        self._items: dict[str, StudentProfile] = {}

    def get(self, student_id: str) -> StudentProfile | None:
        return self._items.get(student_id)

    def save(self, profile: StudentProfile) -> StudentProfile:
        self._items[profile.student_id] = profile
        return profile


class HeuristicProfileExtractor(ProfileExtractor):
    """Profile extraction that works offline and can be replaced by an LLM-backed implementation."""

    def __init__(self, repository: InMemoryProfileRepository):
        self.repository = repository

    async def extract(self, student_id: str, message: str, previous: StudentProfile | None = None) -> StudentProfile:
        old = previous or self.repository.get(student_id)
        lower = message.lower()
        weak_points = []
        interests = []
        if "数学" in message or "公式" in message:
            weak_points.append("数学推导与公式理解")
        if "代码" in message or "实践" in message or "python" in lower:
            interests.append("代码实践")
        if "考试" in message or "题" in message:
            interests.append("练习与应试")
        if "神经网络" in message:
            weak_points.append("神经网络结构")

        dimensions = [
            ProfileDimension(name="知识基础", value="具备 Python 基础，机器学习概念掌握不均衡"),
            ProfileDimension(name="学习目标", value="系统掌握人工智能导论核心知识并能完成课程项目"),
            ProfileDimension(name="认知风格", value="偏好案例驱动、图解说明和循序渐进的解释"),
            ProfileDimension(name="易错点", value="容易混淆模型训练、评估指标和算法适用场景"),
            ProfileDimension(name="学习偏好", value="希望结合短文档、练习题和代码实验学习"),
            ProfileDimension(name="时间投入", value="每周可投入 4-6 小时"),
            ProfileDimension(name="实践能力", value="能够运行基础 Python 代码，需要项目化引导"),
        ]

        profile = StudentProfile(
            student_id=student_id,
            major=old.major if old else "计算机科学与技术",
            course=old.course if old else "人工智能导论",
            dimensions=dimensions,
            weak_points=sorted(set((old.weak_points if old else []) + weak_points)) or ["监督学习流程"],
            interests=sorted(set((old.interests if old else []) + interests)) or ["案例讲解", "代码实践"],
            updated_reason=f"根据最新对话更新：{message[:80]}",
        )
        return self.repository.save(profile)


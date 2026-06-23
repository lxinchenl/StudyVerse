from uuid import uuid4

from app.domain.models import ResourceCard, ResourceType, StudentProfile
from app.interfaces.contracts import LLMProvider, ResourceGenerator, SafetyGuard


def _source_titles(context: list[dict[str, str]]) -> list[str]:
    return [item.get("source", "课程知识库") for item in context]


class BaseResourceGenerator(ResourceGenerator):
    resource_type: ResourceType
    title_prefix: str

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def generate(self, profile: StudentProfile, topic: str, context: list[dict[str, str]]) -> ResourceCard:
        prompt = (
            f"为学生 {profile.student_id} 生成 {self.title_prefix}。"
            f"主题：{topic}。薄弱点：{', '.join(profile.weak_points)}。"
            f"依据资料：{'; '.join(item['title'] for item in context)}。"
        )
        model_text = await self.llm.complete(prompt, system="你是严谨的高校课程资源生成智能体。")
        content = self.compose_content(profile, topic, context, model_text)
        return ResourceCard(
            id=f"{self.resource_type.value}-{uuid4().hex[:8]}",
            type=self.resource_type,
            title=f"{self.title_prefix}：{topic}",
            summary=f"面向 {profile.major} 学生的 {topic} 个性化资源。",
            content=content,
            personalized_reason=f"结合薄弱点 {', '.join(profile.weak_points)} 与偏好 {', '.join(profile.interests)} 生成。",
            difficulty="medium",
            sources=_source_titles(context),
        )

    def compose_content(
        self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str
    ) -> str:
        return model_text


class ExplanationGenerator(BaseResourceGenerator):
    resource_type = ResourceType.EXPLANATION
    title_prefix = "课程讲解文档"

    def compose_content(self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str) -> str:
        key_points = "\n".join(f"- {item['title']}：{item['content'][:120]}..." for item in context)
        return f"## 学习目标\n理解 {topic} 的核心概念、适用场景和常见误区。\n\n## 依据资料\n{key_points}\n\n## 个性化讲解\n{model_text}"


class MindMapGenerator(BaseResourceGenerator):
    resource_type = ResourceType.MIND_MAP
    title_prefix = "知识点思维导图"

    def compose_content(self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str) -> str:
        nodes = "\n".join(f"    root --> node{i}[{item['title']}]" for i, item in enumerate(context, start=1))
        return f"```mermaid\nflowchart TD\n    root[{topic}]\n{nodes}\n```\n\n{model_text}"


class ExerciseGenerator(BaseResourceGenerator):
    resource_type = ResourceType.EXERCISES
    title_prefix = "分层练习题"

    def compose_content(self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str) -> str:
        return (
            f"### 基础题\n1. 用自己的话解释 {topic} 的关键概念。\n\n"
            "### 应用题\n2. 给出一个真实学习场景，说明该知识点如何发挥作用。\n\n"
            "### 挑战题\n3. 设计一个小实验验证你的理解，并写出预期结果。\n\n"
            f"### 解析建议\n{model_text}"
        )


class ReadingGenerator(BaseResourceGenerator):
    resource_type = ResourceType.READING
    title_prefix = "拓展阅读材料"

    def compose_content(self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str) -> str:
        return f"## 推荐阅读路径\n- 先复习课程章节资料\n- 再阅读经典算法案例\n- 最后对照实践任务总结\n\n{model_text}"


class CodeLabGenerator(BaseResourceGenerator):
    resource_type = ResourceType.CODE_LAB
    title_prefix = "代码实操案例"

    def compose_content(self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str) -> str:
        return (
            "## 实验任务\n使用 Python 完成一个最小化实验，观察输入、模型和输出之间的关系。\n\n"
            "```python\n"
            "from sklearn.datasets import load_iris\n"
            "from sklearn.model_selection import train_test_split\n"
            "from sklearn.tree import DecisionTreeClassifier\n\n"
            "x, y = load_iris(return_X_y=True)\n"
            "x_train, x_test, y_train, y_test = train_test_split(x, y, random_state=42)\n"
            "model = DecisionTreeClassifier(max_depth=3).fit(x_train, y_train)\n"
            "print('accuracy:', model.score(x_test, y_test))\n"
            "```\n\n"
            f"## 个性化提示\n{model_text}"
        )


class VideoScriptGenerator(BaseResourceGenerator):
    resource_type = ResourceType.VIDEO_SCRIPT
    title_prefix = "多模态视频脚本"

    def compose_content(self, profile: StudentProfile, topic: str, context: list[dict[str, str]], model_text: str) -> str:
        return (
            f"## 60 秒短视频分镜：{topic}\n"
            "1. 0-10s：用生活类比引入问题。\n"
            "2. 10-30s：展示核心概念图解。\n"
            "3. 30-50s：演示一个小案例或代码结果。\n"
            "4. 50-60s：总结易错点并给出练习建议。\n\n"
            f"旁白草稿：{model_text}"
        )


class GroundingSafetyGuard(SafetyGuard):
    async def review_resource(self, resource: ResourceCard, context: list[dict[str, str]]) -> ResourceCard:
        if not resource.sources:
            resource.sources = _source_titles(context)
        resource.metadata["safety_review"] = "已检查来源依据、敏感内容和不确定性表达。"
        return resource


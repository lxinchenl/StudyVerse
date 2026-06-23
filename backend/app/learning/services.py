from app.domain.models import EvaluationReport, LearningPathStep, ResourceCard, StudentProfile
from app.interfaces.contracts import LearningEvaluator, LearningPathPlanner


class RuleBasedLearningPathPlanner(LearningPathPlanner):
    async def plan(self, profile: StudentProfile, resources: list[ResourceCard]) -> list[LearningPathStep]:
        resource_ids = [resource.id for resource in resources]
        weak_point = profile.weak_points[0] if profile.weak_points else "核心概念"
        return [
            LearningPathStep(
                id="step-1",
                title=f"补齐基础：{weak_point}",
                objective="先建立关键术语、基本流程和常见误区的稳定理解。",
                reason="画像显示该主题是当前薄弱点，适合先用讲解文档和思维导图降低理解成本。",
                estimated_minutes=35,
                resources=resource_ids[:2],
                checkpoint="能够用 3 句话解释核心概念，并指出一个常见误区。",
            ),
            LearningPathStep(
                id="step-2",
                title="练习巩固与错因定位",
                objective="通过分层练习暴露知识盲区，形成可反馈的学习证据。",
                reason="练习题能帮助系统判断掌握度，并驱动后续资源推送。",
                estimated_minutes=45,
                resources=resource_ids[2:3],
                checkpoint="完成基础题和应用题，正确率达到 80%。",
            ),
            LearningPathStep(
                id="step-3",
                title="实践迁移与项目化应用",
                objective="用代码案例或短视频脚本把知识迁移到真实任务。",
                reason="画像显示学生偏好案例和代码实践，实践任务可增强长期记忆。",
                estimated_minutes=60,
                resources=resource_ids[3:],
                checkpoint="能运行代码案例，并说明实验结果代表什么。",
            ),
        ]


class RuleBasedLearningEvaluator(LearningEvaluator):
    async def evaluate(self, profile: StudentProfile, activity: dict) -> EvaluationReport:
        completed = float(activity.get("completed_resources", 2))
        correct_rate = float(activity.get("correct_rate", 0.76))
        mastery = {
            "概念理解": min(0.95, 0.55 + completed * 0.08),
            "算法应用": correct_rate,
            "代码实践": 0.68 if "代码实践" in profile.interests else 0.58,
            "知识迁移": 0.62,
        }
        weaknesses = [key for key, value in mastery.items() if value < 0.7]
        return EvaluationReport(
            student_id=profile.student_id,
            mastery=mastery,
            strengths=[key for key, value in mastery.items() if value >= 0.75],
            weaknesses=weaknesses or profile.weak_points[:1],
            recommendations=[
                "优先复盘低于 70% 的能力维度。",
                "完成代码实操后提交运行结果和反思。",
                "下一轮资源推送应增加图解与错题讲评。",
            ],
        )


"""专家 Agent 注册表，供 MainAgent ReAct 与 Orchestrator 共用。"""

EXPERT_AGENTS: dict[str, str] = {
    "retrieval-agent": "检索课程资料与知识图谱",
    "exercise-agent": "查找/生成练习题（search 匹配题库，generate 基于检索生成）",
    "note-agent": "生成结构化笔记",
    "mindmap-agent": "基于资料生成 Mermaid 思维导图",
    "video-agent": "生成 HTML 讲解动画 + 本地配音（需先获取课程资料）",
    "code-lab-agent": "生成 Python 编程题（沙箱判题）",
    "path-agent": "规划学习路径",
    "course-workflow-agent": "编排定制系统课并同步学习路径",
    "safety-agent": "安全审校（来源校验 / 敏感内容）",
}

MAX_REACT_STEPS = 6

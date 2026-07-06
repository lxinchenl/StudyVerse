type QuestionMetaTagsProps = {
  difficulty?: string;
  gradingType?: string;
};

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "简单",
  medium: "中等",
  hard: "困难"
};

const GRADING_TYPE_LABELS: Record<string, string> = {
  standard: "标准答案",
  rubric: "开放题"
};

function normalizeTagValue(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-") || "unknown";
}

export function QuestionMetaTags({ difficulty, gradingType }: QuestionMetaTagsProps) {
  const difficultyValue = difficulty || "unknown";
  const gradingTypeValue = gradingType || "standard";
  const normalizedDifficulty = normalizeTagValue(difficultyValue);
  const normalizedGradingType = normalizeTagValue(gradingTypeValue);

  return (
    <span className="question-meta-tags">
      <span className={`question-tag question-tag--difficulty question-tag--difficulty-${normalizedDifficulty}`}>
        {DIFFICULTY_LABELS[normalizedDifficulty] ?? difficultyValue}
      </span>
      <span className={`question-tag question-tag--type question-tag--type-${normalizedGradingType}`}>
        {GRADING_TYPE_LABELS[normalizedGradingType] ?? gradingTypeValue}
      </span>
    </span>
  );
}

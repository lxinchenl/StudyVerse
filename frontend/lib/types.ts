export type DocType = "pdf" | "pptx" | "docx" | "markdown" | "txt" | "code";

export type ResourceType =
  | "exercise"
  | "note"
  | "mindmap"
  | "video_script"
  | "code_lab";

export type AgentStatus = "pending" | "running" | "done" | "failed" | "retry";

export interface Course {
  id: string;
  title: string;
  description: string;
  progress: number;
  lastStudiedAt: string;
  chapterCount: number;
  documentCount: number;
}

export interface Chapter {
  id: string;
  courseId: string;
  title: string;
  order: number;
}

export interface CourseDocument {
  id: string;
  courseId: string;
  chapterId: string;
  title: string;
  type: DocType;
  pages?: number;
  progress: number;
  content?: string;
  fileName?: string;
  fileUrl?: string;
}

export interface UserProfile {
  major: string;
  course: string;
  goal: string;
  recentTopics: string[];
  weakPoints: string[];
  frequentErrors: string[];
  preferences: string[];
}

export interface ExplainerVideo {
  resourceId: string;
  title: string;
  summary: string;
  playerUrl: string;
  sceneCount: number;
}

export interface ExerciseQuestion {
  id: string;
  topic: string;
  difficulty: string;
  question: string;
  gradingType: "standard" | "rubric" | string;
  attemptStatus?: "unanswered" | "correct" | "wrong" | string;
  lastScore?: number | null;
}

export interface ExerciseSet {
  resourceId: string;
  title: string;
  topic: string;
  summary: string;
  questions: ExerciseQuestion[];
}

export interface ReactStep {
  step?: number;
  thought: string;
  action: string;
  expert?: string;
  tool?: string;
  skill?: string;
  observation?: string;
  status?: "pending" | "running" | "done" | string;
  exercise?: { mode?: string; topic?: string };
  codeLab?: { mode?: string; topic?: string };
}

export interface MainAgentContext {
  step: number;
  updatedAt: string;
  message: string;
  promptText: string;
  materialSummary: string;
  explicitMemory: Array<{ type?: string; content?: string; created_at?: string }>;
  sessionDialogue: Array<{ role?: string; content?: string; time?: string }>;
  retrieval: {
    queries: string[];
    entities: string[];
    sourceTypes: string[];
    mergeBoundary?: {
      search_chunks?: number;
      document_chunks?: number;
      max_search_chunks?: number;
      max_document_chunks?: number;
    };
    summarized?: {
      trigger_chars?: number;
      target_chars?: number;
      agent?: string;
    };
    chunks: Array<{
      index: number;
      chunkId?: string;
      title?: string;
      sourceType?: string;
      source?: string;
      score?: number;
      text: string;
    }>;
  };
  reactSteps: ReactStep[];
}

export interface MindmapResource {
  resourceId: string;
  title: string;
  topic: string;
  summary: string;
  mermaidSource: string;
}

export interface NoteResource {
  resourceId: string;
  title: string;
  topic: string;
  summary: string;
  markdown: string;
}

export interface CodeLabChallenge {
  id: string;
  topic: string;
  difficulty: string;
  question: string;
  starterCode: string;
  setupCode: string;
  language: string;
  hint: string;
  attemptStatus?: string;
  lastScore?: number | null;
}

export interface CodeLabSet {
  resourceId: string;
  title: string;
  topic: string;
  summary: string;
  challenges: CodeLabChallenge[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  agentTraces?: AgentTrace[];
  reactSteps?: ReactStep[];
  streamStatus?: string;
  retrieval?: ChatRetrieval;
  explainerVideos?: ExplainerVideo[];
  exerciseSets?: ExerciseSet[];
  mindmaps?: MindmapResource[];
  notes?: NoteResource[];
  codeLabSets?: CodeLabSet[];
  courseProposalCard?: CourseProposalCard;
}

export interface CourseProposalModule {
  id: string;
  title: string;
  objective: string;
  chapterKey: string;
  estimatedMinutes: number;
  topics: string[];
}

export interface CourseProposalCard {
  kind: "course_proposal";
  status: "pending" | "confirmed" | "cancelled";
  topic: string;
  courseTitle: string;
  summary: string;
  modules: CourseProposalModule[];
}

export interface AgentTrace {
  agent: string;
  role: string;
  status: AgentStatus;
  summary: string;
  durationMs?: number;
}

export interface ChatRetrievalChunk {
  chunkId?: string;
  title: string;
  text: string;
  source?: string;
  score?: number;
}

export interface ChatRetrieval {
  query?: string;
  queries: string[];
  entities: string[];
  sourceTypes: string[];
  chunks: ChatRetrievalChunk[];
  kgContext: Array<{ source: string; relation: string; target: string }>;
}

export interface LearningPathStep {
  id: string;
  title: string;
  objective: string;
  status: "pending" | "in_progress" | "done";
  estimatedMinutes: number;
  resources: string[];
}

export interface CourseResourceRef {
  type: ResourceType | string;
  resourceId: string;
  title: string;
  order: number;
  learningOrderReason?: string;
}

export interface LearningModule {
  id: string;
  title: string;
  objective: string;
  status: "pending" | "in_progress" | "done";
  estimatedMinutes: number;
  chapterKey: string;
  resources: CourseResourceRef[];
}

export interface LearningCourseSummary {
  id: string;
  title: string;
  topic: string;
  summary: string;
  status: string;
  moduleCount: number;
  progress: number;
  createdAt: string;
}

export interface LearningCourseDetail {
  id: string;
  title: string;
  topic: string;
  summary: string;
  status: string;
  createdAt: string;
  modules: LearningModule[];
}

export interface Exercise {
  id: string;
  resourceId: string;
  resourceTitle: string;
  topic: string;
  difficulty: string;
  question: string;
  standardAnswer: string;
  gradingType?: "standard" | "rubric" | string;
}

export interface ExerciseSubmission {
  questionId: string;
  userAnswer: string;
  score: number;
  submittedAt: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: "Course" | "Chapter" | "KnowledgePoint" | "Document" | "Exercise";
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
}

export interface KnowledgeGraphMeta {
  backend: string;
  neo4jConnected: boolean;
  nodeCount: number;
  edgeCount: number;
}

export interface KnowledgeGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta?: KnowledgeGraphMeta;
}

export interface GeneratedResource {
  id: string;
  type: ResourceType;
  title: string;
  summary: string;
  content: string;
  topic: string;
  createdAt: string;
  playerUrl?: string;
  sceneCount?: number;
}

export interface PlannerTask {
  id: string;
  name: string;
  agent: string;
  status: AgentStatus;
  parallel: boolean;
  inputSummary: string;
  outputSummary?: string;
}

export interface ReadingContext {
  courseId: string;
  documentId: string;
  page?: number;
  section?: string;
  selectedText?: string;
}

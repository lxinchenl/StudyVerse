import type {
  Chapter,
  ChatMessage,
  CodeLabSet,
  Course,
  CourseDocument,
  CourseProposalCard,
  Exercise,
  GeneratedResource,
  GraphEdge,
  GraphNode,
  KnowledgeGraphData,
  LearningPathStep,
  LearningCourseSummary,
  LearningCourseDetail,
  LearningModule,
  CourseResourceRef,
  MainAgentContext,
  UserProfile
} from "./types";

import { API_BASE } from "./constants";

export interface ApiUser {
  id: string;
  name: string;
  major: string;
  email: string;
}

function parseApiError(text: string): string {
  try {
    const data = JSON.parse(text) as { detail?: string };
    if (typeof data.detail === "string") return data.detail;
  } catch {
    /* not json */
  }
  return text || "请求失败";
}

type ApiProfile = {
  student_id: string;
  major: string;
  course: string;
  goal: string;
  recent_topics: string[];
  weak_points: string[];
  frequent_errors: string[];
  preferences: string[];
  mastery: Record<string, number>;
};

function mapExplainerVideos(
  rows?: Array<{
    resource_id: string;
    title: string;
    summary: string;
    player_url: string;
    scene_count?: number;
  }>
) {
  if (!rows?.length) return undefined;
  return rows.map((v) => ({
    resourceId: v.resource_id,
    title: v.title,
    summary: v.summary,
    playerUrl: v.player_url,
    sceneCount: v.scene_count ?? 0
  }));
}

function mapExerciseSets(
  rows?: Array<{
    resource_id: string;
    title: string;
    topic: string;
    summary: string;
    questions?: Array<{
      id: string;
      topic: string;
      difficulty: string;
      question: string;
      grading_type?: string;
      attempt_status?: string;
      last_score?: number | null;
    }>;
  }>
) {
  if (!rows?.length) return undefined;
  return rows.map((set) => ({
    resourceId: set.resource_id,
    title: set.title,
    topic: set.topic,
    summary: set.summary,
    questions: (set.questions ?? []).map((q) => ({
      id: q.id,
      topic: q.topic,
      difficulty: q.difficulty,
      question: q.question,
      gradingType: q.grading_type ?? "standard",
      attemptStatus: q.attempt_status,
      lastScore: q.last_score
    }))
  }));
}

function mapMindmaps(
  rows?: Array<{
    resource_id: string;
    title: string;
    topic: string;
    summary: string;
    mermaid_source: string;
  }>
) {
  if (!rows?.length) return undefined;
  return rows.map((m) => ({
    resourceId: m.resource_id,
    title: m.title,
    topic: m.topic,
    summary: m.summary,
    mermaidSource: m.mermaid_source
  }));
}

function mapNotes(
  rows?: Array<{
    resource_id: string;
    title: string;
    topic: string;
    summary: string;
    markdown: string;
  }>
) {
  if (!rows?.length) return undefined;
  return rows.map((n) => ({
    resourceId: n.resource_id,
    title: n.title,
    topic: n.topic,
    summary: n.summary,
    markdown: n.markdown
  }));
}

function mapCodeLabSets(
  rows?: Array<{
    resource_id: string;
    title: string;
    topic: string;
    summary: string;
    challenges?: Array<{
      id: string;
      topic: string;
      difficulty: string;
      question: string;
      starter_code?: string;
      setup_code?: string;
      language?: string;
      hint?: string;
      attempt_status?: string;
      last_score?: number | null;
    }>;
  }>
) {
  if (!rows?.length) return undefined;
  return rows.map((s) => ({
    resourceId: s.resource_id,
    title: s.title,
    topic: s.topic,
    summary: s.summary,
    challenges: (s.challenges ?? []).map((c) => ({
      id: c.id,
      topic: c.topic,
      difficulty: c.difficulty,
      question: c.question,
      starterCode: c.starter_code ?? "",
      setupCode: c.setup_code ?? "",
      language: c.language ?? "python",
      hint: c.hint ?? "",
      attemptStatus: c.attempt_status,
      lastScore: c.last_score
    }))
  }));
}

function mapProfile(p: ApiProfile): UserProfile {
  return {
    major: p.major,
    course: p.course,
    goal: p.goal,
    recentTopics: p.recent_topics,
    weakPoints: p.weak_points,
    frequentErrors: p.frequent_errors,
    preferences: p.preferences
  };
}

async function request<T>(path: string, userId?: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined)
  };
  if (userId) headers["X-User-Id"] = userId;

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(parseApiError(text) || `API ${response.status}: ${path}`);
  }
  return response.json();
}

export async function loginUser(email: string, password: string): Promise<ApiUser> {
  return request<ApiUser>("/auth/login", undefined, {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export async function registerUser(
  name: string,
  email: string,
  password: string,
  major: string = ""
): Promise<ApiUser> {
  return request<ApiUser>("/auth/register", undefined, {
    method: "POST",
    body: JSON.stringify({ name, email, password, major })
  });
}

export async function fetchCurrentUser(userId: string): Promise<ApiUser> {
  return request<ApiUser>("/auth/me", userId);
}

export interface UserUploadResult {
  filename: string;
  relativePath: string;
  size: number;
}

export async function uploadUserFile(userId: string, file: File): Promise<UserUploadResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/users/uploads`, {
    method: "POST",
    headers: { "X-User-Id": userId },
    body: form
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(parseApiError(text) || `上传失败: ${response.status}`);
  }
  const data = (await response.json()) as {
    filename: string;
    relative_path: string;
    size: number;
  };
  return {
    filename: data.filename,
    relativePath: data.relative_path,
    size: data.size
  };
}

export async function fetchProfile(userId: string): Promise<UserProfile> {
  const data = await request<ApiProfile>("/profile", userId);
  return mapProfile(data);
}

export async function fetchCourses(userId: string): Promise<Course[]> {
  const rows = await request<
    Array<{
      id: string;
      title: string;
      description: string;
      progress: number;
      last_studied_at: string;
      chapter_count: number;
      document_count: number;
    }>
  >("/courses", userId);
  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    description: r.description,
    progress: r.progress,
    lastStudiedAt: r.last_studied_at,
    chapterCount: r.chapter_count,
    documentCount: r.document_count
  }));
}

export async function fetchChapters(courseId: string): Promise<Chapter[]> {
  const rows = await request<Array<{ id: string; course_id: string; title: string; order: number }>>(
    `/courses/${courseId}/chapters`
  );
  return rows.map((r) => ({
    id: r.id,
    courseId: r.course_id,
    title: r.title,
    order: r.order
  }));
}

export async function fetchDocuments(courseId: string, userId: string): Promise<CourseDocument[]> {
  const rows = await request<
    Array<{
      id: string;
      course_id: string;
      chapter_id: string;
      title: string;
      type: string;
      pages?: number;
      progress: number;
      content?: string;
      file_name?: string;
      file_url?: string;
    }>
  >(`/courses/${courseId}/documents`, userId);
  return rows.map((r) => ({
    id: r.id,
    courseId: r.course_id,
    chapterId: r.chapter_id,
    title: r.title,
    type: r.type as CourseDocument["type"],
    pages: r.pages,
    progress: r.progress,
    content: r.content,
    fileName: r.file_name,
    fileUrl: r.file_url
  }));
}

export async function fetchDocument(docId: string, userId: string): Promise<CourseDocument> {
  const r = await request<{
    id: string;
    course_id: string;
    chapter_id: string;
    title: string;
    type: string;
    pages?: number;
    progress: number;
    content?: string;
    file_name?: string;
    file_url?: string;
  }>(`/documents/${docId}`, userId);
  return {
    id: r.id,
    courseId: r.course_id,
    chapterId: r.chapter_id,
    title: r.title,
    type: r.type as CourseDocument["type"],
    pages: r.pages,
    progress: r.progress,
    content: r.content,
    fileName: r.file_name,
    fileUrl: r.file_url
  };
}

export async function markDocumentProgress(
  userId: string,
  docId: string,
  payload: {
    viewedPage?: number;
    totalPages?: number;
    completed?: boolean;
  }
): Promise<{ documentProgress: number; courseProgress: number; lastStudiedAt: string }> {
  const data = await request<{
    document_progress: number;
    course_progress: number;
    last_studied_at: string;
  }>(`/documents/${encodeURIComponent(docId)}/progress`, userId, {
    method: "POST",
    body: JSON.stringify({
      viewed_page: payload.viewedPage,
      total_pages: payload.totalPages,
      completed: Boolean(payload.completed)
    })
  });
  return {
    documentProgress: data.document_progress,
    courseProgress: data.course_progress,
    lastStudiedAt: data.last_studied_at
  };
}

function mapReactSteps(
  steps?: Array<{
    step?: number;
    thought?: string;
    action?: string;
    expert?: string;
    tool?: string;
    skill?: string;
    observation?: string;
    status?: string;
  }>
) {
  if (!steps?.length) return undefined;
  return steps.map((s) => ({
    step: s.step,
    thought: s.thought ?? "",
    action: s.action ?? "",
    expert: s.expert,
    tool: s.tool,
    skill: s.skill,
    observation: s.observation,
    status: s.status
  }));
}

function mapAgentTraces(
  traces?: Array<{ agent: string; role: string; summary: string; status: string }>
) {
  return traces?.map((t) => ({
    agent: t.agent,
    role: t.role,
    status: t.status as ChatMessage["agentTraces"] extends (infer U)[] | undefined
      ? U extends { status: infer S }
        ? S
        : never
      : never,
    summary: t.summary
  }));
}

function mapRetrieval(
  retrieval?: {
    query?: string;
    queries?: string[];
    entities?: string[];
    source_types?: string[];
    chunks?: Array<{
      chunk_id?: string;
      title?: string;
      text?: string;
      source?: string;
      score?: number;
    }>;
    kg_context?: Array<{ source: string; relation: string; target: string }>;
  } | null
) {
  if (!retrieval) return undefined;
  return {
    query: retrieval.query,
    queries: retrieval.queries ?? [],
    entities: retrieval.entities ?? [],
    sourceTypes: retrieval.source_types ?? [],
    chunks: (retrieval.chunks ?? []).map((c) => ({
      chunkId: c.chunk_id,
      title: c.title ?? "",
      text: c.text ?? "",
      source: c.source,
      score: c.score
    })),
    kgContext: retrieval.kg_context ?? []
  };
}

type ApiMainAgentContext = {
  step?: number;
  updated_at?: string;
  message?: string;
  prompt_text?: string;
  system_text?: string;
  user_prompt_text?: string;
  material_summary?: string;
  explicit_memory?: Array<{ type?: string; content?: string; created_at?: string }>;
  session_dialogue?: Array<{ role?: string; content?: string; time?: string }>;
  retrieval?: {
    queries?: string[];
    entities?: string[];
    source_types?: string[];
    merge_boundary?: MainAgentContext["retrieval"]["mergeBoundary"];
    summarized?: MainAgentContext["retrieval"]["summarized"];
    chunks?: Array<{
      index?: number;
      chunk_id?: string;
      title?: string;
      source_type?: string;
      source?: string;
      score?: number;
      text?: string;
    }>;
  };
  react_steps?: Array<{
    step?: number;
    thought?: string;
    action?: string;
    expert?: string;
    tool?: string;
    skill?: string;
    observation?: string;
    status?: string;
  }>;
};

export function mapMainAgentContext(raw?: ApiMainAgentContext | null): MainAgentContext | null {
  if (!raw) return null;
  return {
    step: raw.step ?? 1,
    updatedAt: raw.updated_at ?? "",
    message: raw.message ?? "",
    promptText: raw.prompt_text ?? "",
    systemText: raw.system_text ?? "",
    userPromptText: raw.user_prompt_text ?? raw.prompt_text ?? "",
    materialSummary: raw.material_summary ?? "",
    explicitMemory: raw.explicit_memory ?? [],
    sessionDialogue: raw.session_dialogue ?? [],
    retrieval: {
      queries: raw.retrieval?.queries ?? [],
      entities: raw.retrieval?.entities ?? [],
      sourceTypes: raw.retrieval?.source_types ?? [],
      mergeBoundary: raw.retrieval?.merge_boundary,
      summarized: raw.retrieval?.summarized,
      chunks: (raw.retrieval?.chunks ?? []).map((c, i) => ({
        index: c.index ?? i + 1,
        chunkId: c.chunk_id,
        title: c.title,
        sourceType: c.source_type,
        source: c.source,
        score: c.score,
        text: c.text ?? ""
      }))
    },
    reactSteps: mapReactSteps(raw.react_steps) ?? []
  };
}

export async function fetchMainAgentContext(userId: string): Promise<MainAgentContext | null> {
  const raw = await request<ApiMainAgentContext>("/chat/main-context", userId);
  return mapMainAgentContext(raw);
}

type ApiCourseProposalCard = {
  kind?: string;
  status?: string;
  topic?: string;
  course_title?: string;
  summary?: string;
  modules?: Array<{
    id?: string;
    title?: string;
    objective?: string;
    chapter_key?: string;
    estimated_minutes?: number;
    topics?: string[];
  }>;
};

export function mapCourseProposalCard(raw?: ApiCourseProposalCard | null): CourseProposalCard | undefined {
  if (!raw || raw.kind !== "course_proposal") return undefined;
  return {
    kind: "course_proposal",
    status: (raw.status as CourseProposalCard["status"]) || "pending",
    topic: raw.topic ?? "",
    courseTitle: raw.course_title ?? "",
    summary: raw.summary ?? "",
    modules: (raw.modules ?? []).map((mod, index) => ({
      id: mod.id ?? `mod-${index + 1}`,
      title: mod.title ?? "",
      objective: mod.objective ?? "",
      chapterKey: mod.chapter_key ?? "",
      estimatedMinutes: mod.estimated_minutes ?? 45,
      topics: mod.topics ?? []
    }))
  };
}

export async function fetchChatHistory(userId: string): Promise<ChatMessage[]> {
  const rows = await request<
    Array<{
      id: string;
      role: string;
      content: string;
      timestamp: string;
      agent_traces?: Array<{ agent: string; role: string; summary: string; status: string }>;
      react_steps?: Array<{
        step?: number;
        thought?: string;
        action?: string;
        expert?: string;
        tool?: string;
        skill?: string;
        observation?: string;
        status?: string;
      }>;
      explainer_videos?: Array<{
        resource_id: string;
        title: string;
        summary: string;
        player_url: string;
        scene_count?: number;
      }>;
      exercise_sets?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        questions?: Array<{
          id: string;
          topic: string;
          difficulty: string;
          question: string;
          grading_type?: string;
          attempt_status?: string;
          last_score?: number | null;
        }>;
      }>;
      mindmaps?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        mermaid_source: string;
      }>;
      notes?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        markdown: string;
      }>;
      code_lab_sets?: Parameters<typeof mapCodeLabSets>[0];
      retrieval?: Parameters<typeof mapRetrieval>[0];
      course_proposal_card?: ApiCourseProposalCard;
    }>
  >("/chat/history?limit=50", userId);
  return rows.map((r) => ({
    id: r.id,
    role: r.role as ChatMessage["role"],
    content: r.content,
    timestamp: r.timestamp,
    agentTraces: mapAgentTraces(r.agent_traces),
    reactSteps: mapReactSteps(r.react_steps),
    retrieval: mapRetrieval(r.retrieval),
    explainerVideos: mapExplainerVideos(r.explainer_videos),
    exerciseSets: mapExerciseSets(r.exercise_sets),
    mindmaps: mapMindmaps(r.mindmaps),
    notes: mapNotes(r.notes),
    codeLabSets: mapCodeLabSets(r.code_lab_sets),
    courseProposalCard: mapCourseProposalCard(r.course_proposal_card)
  }));
}

export async function clearChatHistory(userId: string): Promise<void> {
  await request("/chat/history", userId, { method: "DELETE" });
}

export async function clearShortTermMemory(userId: string): Promise<void> {
  await request("/memory/clear-short-term", userId, { method: "POST" });
}

export async function sendChat(
  userId: string,
  message: string,
  options?: { courseId?: string; documentId?: string; selectedText?: string }
): Promise<{ messages: ChatMessage[]; profile: UserProfile }> {
  const data = await request<{
    messages: Array<{
      id: string;
      role: string;
      content: string;
      timestamp: string;
      agent_traces?: Array<{ agent: string; role: string; summary: string; status: string }>;
      react_steps?: Array<{
        step?: number;
        thought?: string;
        action?: string;
        expert?: string;
        tool?: string;
        skill?: string;
        observation?: string;
        status?: string;
      }>;
      retrieval?: {
        query?: string;
        source_types?: string[];
        chunks?: Array<{
          chunk_id?: string;
          title?: string;
          text?: string;
          source?: string;
          score?: number;
        }>;
        kg_context?: Array<{ source: string; relation: string; target: string }>;
      } | null;
      explainer_videos?: Array<{
        resource_id: string;
        title: string;
        summary: string;
        player_url: string;
        scene_count?: number;
      }>;
      exercise_sets?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        questions?: Array<{
          id: string;
          topic: string;
          difficulty: string;
          question: string;
          grading_type?: string;
          attempt_status?: string;
          last_score?: number | null;
        }>;
      }>;
      mindmaps?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        mermaid_source: string;
      }>;
      notes?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        markdown: string;
      }>;
      code_lab_sets?: Parameters<typeof mapCodeLabSets>[0];
    }>;
    profile: ApiProfile;
  }>("/chat", userId, {
    method: "POST",
    body: JSON.stringify({
      message,
      course_id: options?.courseId,
      document_id: options?.documentId,
      selected_text: options?.selectedText
    })
  });
  return {
    messages: data.messages.map((r) => ({
      id: r.id,
      role: r.role as ChatMessage["role"],
      content: r.content,
      timestamp: r.timestamp,
      agentTraces: mapAgentTraces(r.agent_traces),
      reactSteps: mapReactSteps(r.react_steps),
      retrieval: mapRetrieval(r.retrieval),
      explainerVideos: mapExplainerVideos(r.explainer_videos),
      exerciseSets: mapExerciseSets(r.exercise_sets),
      mindmaps: mapMindmaps(r.mindmaps),
      notes: mapNotes(r.notes),
      codeLabSets: mapCodeLabSets(r.code_lab_sets)
    })),
    profile: mapProfile(data.profile)
  };
}

export type ChatStreamEvent =
  | { type: "status"; message: string }
  | { type: "answer_start"; message_id?: string }
  | { type: "answer_delta"; delta: string }
  | {
      type: "progress";
      react_steps?: Array<{
        step?: number;
        thought?: string;
        action?: string;
        expert?: string;
        tool?: string;
        skill?: string;
        observation?: string;
        status?: string;
      }>;
      traces?: Array<{ agent: string; role: string; summary: string; status: string }>;
      exercise_sets?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        questions?: Array<{
          id: string;
          topic: string;
          difficulty: string;
          question: string;
          grading_type?: string;
          attempt_status?: string;
          last_score?: number | null;
        }>;
      }>;
      mindmaps?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        mermaid_source: string;
      }>;
      notes?: Array<{
        resource_id: string;
        title: string;
        topic: string;
        summary: string;
        markdown: string;
      }>;
      code_lab_sets?: Parameters<typeof mapCodeLabSets>[0];
      course_proposal_card?: ApiCourseProposalCard;
      main_context?: ApiMainAgentContext;
    }
  | {
      type: "done";
      messages: Array<{
        id: string;
        role: string;
        content: string;
        timestamp: string;
        agent_traces?: Array<{ agent: string; role: string; summary: string; status: string }>;
        react_steps?: Array<{
          step?: number;
          thought?: string;
          action?: string;
          expert?: string;
          tool?: string;
          skill?: string;
          observation?: string;
          status?: string;
        }>;
        retrieval?: Parameters<typeof mapRetrieval>[0];
        explainer_videos?: Array<{
          resource_id: string;
          title: string;
          summary: string;
          player_url: string;
          scene_count?: number;
        }>;
        exercise_sets?: Array<{
          resource_id: string;
          title: string;
          topic: string;
          summary: string;
          questions?: Array<{
            id: string;
            topic: string;
            difficulty: string;
            question: string;
            grading_type?: string;
            attempt_status?: string;
            last_score?: number | null;
          }>;
        }>;
        mindmaps?: Array<{
          resource_id: string;
          title: string;
          topic: string;
          summary: string;
          mermaid_source: string;
        }>;
        notes?: Array<{
          resource_id: string;
          title: string;
          topic: string;
          summary: string;
          markdown: string;
        }>;
        code_lab_sets?: Parameters<typeof mapCodeLabSets>[0];
        course_proposal_card?: ApiCourseProposalCard;
      }>;
      profile: ApiProfile;
    }
  | { type: "error"; message: string };

export async function sendChatStream(
  userId: string,
  message: string,
  onEvent: (event: ChatStreamEvent) => void,
  options?: {
    courseId?: string;
    documentId?: string;
    selectedText?: string;
    courseWorkflowAction?: "confirm" | "cancel";
    courseProposal?: Record<string, unknown>;
  }
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-User-Id": userId
  };
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      course_id: options?.courseId,
      document_id: options?.documentId,
      selected_text: options?.selectedText,
      course_workflow_action: options?.courseWorkflowAction,
      course_proposal: options?.courseProposal
    })
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API ${response.status}: /chat/stream`);
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("流式响应不可用");

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let splitAt = buffer.indexOf("\n\n");
    while (splitAt !== -1) {
      const chunk = buffer.slice(0, splitAt);
      buffer = buffer.slice(splitAt + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const event = JSON.parse(line.slice(6)) as ChatStreamEvent;
        if (event.type === "error") {
          throw new Error(event.message);
        }
        onEvent(event);
      }
      splitAt = buffer.indexOf("\n\n");
    }
  }
}

export async function fetchKnowledgeGraph(): Promise<KnowledgeGraphData> {
  const data = await request<{
    nodes: GraphNode[];
    edges: GraphEdge[];
    meta?: {
      backend: string;
      neo4j_connected: boolean;
      node_count: number;
      edge_count: number;
    };
  }>("/knowledge-graph");
  return {
    nodes: data.nodes,
    edges: data.edges,
    meta: data.meta
      ? {
          backend: data.meta.backend,
          neo4jConnected: data.meta.neo4j_connected,
          nodeCount: data.meta.node_count,
          edgeCount: data.meta.edge_count,
        }
      : undefined,
  };
}

export type PracticeResource = {
  id: string;
  title: string;
  kind: "exercise" | "code_lab";
  updatedAt?: number;
};

export async function fetchPracticeResources(): Promise<PracticeResource[]> {
  const rows = await request<Array<{ id: string; title: string; kind?: string; updated_at?: number }>>(
    "/practice/resources"
  );
  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    kind: r.kind === "code_lab" ? "code_lab" : "exercise",
    updatedAt: r.updated_at
  }));
}

/** @deprecated use fetchPracticeResources */
export const fetchExerciseResources = fetchPracticeResources;

export async function fetchExercises(resourceId: string): Promise<Exercise[]> {
  const rows = await request<
    Array<{
      id: string;
      resource_id: string;
      resource_title: string;
      topic: string;
      difficulty: string;
      question: string;
      grading_type?: string;
    }>
  >(`/practice/questions?resource_id=${encodeURIComponent(resourceId)}`);
  return rows.map((r) => ({
    id: r.id,
    resourceId: r.resource_id,
    resourceTitle: r.resource_title,
    topic: r.topic,
    difficulty: r.difficulty,
    question: r.question,
    standardAnswer: "",
    gradingType: r.grading_type ?? "standard"
  }));
}

export async function fetchCodeLabSet(userId: string, resourceId: string): Promise<CodeLabSet> {
  const data = await request<{
    resource_id: string;
    title: string;
    topic: string;
    summary: string;
    challenges?: Array<{
      id: string;
      topic: string;
      difficulty: string;
      question: string;
      starter_code?: string;
      setup_code?: string;
      language?: string;
      hint?: string;
      attempt_status?: string;
      last_score?: number | null;
    }>;
  }>(`/code-lab/set?resource_id=${encodeURIComponent(resourceId)}`, userId);
  return {
    resourceId: data.resource_id,
    title: data.title,
    topic: data.topic,
    summary: data.summary,
    challenges: (data.challenges ?? []).map((c) => ({
      id: c.id,
      topic: c.topic,
      difficulty: c.difficulty,
      question: c.question,
      starterCode: c.starter_code ?? "",
      setupCode: c.setup_code ?? "",
      language: c.language ?? "python",
      hint: c.hint ?? "",
      attemptStatus: c.attempt_status,
      lastScore: c.last_score
    }))
  };
}

export async function runCodeLab(
  userId: string,
  resourceId: string,
  challengeId: string,
  code: string
): Promise<{ ok: boolean; stdout: string; stderr: string; exitCode: number; error: string }> {
  const data = await request<{
    ok: boolean;
    stdout: string;
    stderr: string;
    exit_code: number;
    error?: string;
  }>(`/code-lab/run?resource_id=${encodeURIComponent(resourceId)}`, userId, {
    method: "POST",
    body: JSON.stringify({ challenge_id: challengeId, code })
  });
  return {
    ok: data.ok,
    stdout: data.stdout,
    stderr: data.stderr,
    exitCode: data.exit_code,
    error: data.error ?? ""
  };
}

export async function submitCodeLab(
  userId: string,
  resourceId: string,
  answers: Record<string, string>
): Promise<{
  totalScore: number;
  results: Array<{
    challengeId: string;
    score: number;
    passed: boolean;
    expectedStdout: string;
    actualStdout: string;
    feedback: string;
  }>;
  profile: UserProfile;
}> {
  const data = await request<{
    total_score: number;
    results: Array<{
      challenge_id: string;
      score: number;
      passed: boolean;
      expected_stdout?: string;
      actual_stdout?: string;
      feedback?: string;
    }>;
    profile: ApiProfile;
  }>(`/code-lab/submit?resource_id=${encodeURIComponent(resourceId)}`, userId, {
    method: "POST",
    body: JSON.stringify({ answers })
  });
  return {
    totalScore: data.total_score,
    results: data.results.map((r) => ({
      challengeId: r.challenge_id,
      score: r.score,
      passed: r.passed,
      expectedStdout: r.expected_stdout ?? "",
      actualStdout: r.actual_stdout ?? "",
      feedback: r.feedback ?? ""
    })),
    profile: mapProfile(data.profile)
  };
}

export async function submitPractice(
  userId: string,
  resourceId: string,
  answers: Record<string, string>
): Promise<{
  totalScore: number;
  results: Array<{
    questionId: string;
    score: number;
    standardAnswer: string;
    gradingType: string;
    feedback: string;
  }>;
  profile: UserProfile;
}> {
  const data = await request<{
    total_score: number;
    results: Array<{
      question_id: string;
      score: number;
      standard_answer: string;
      grading_type?: string;
      feedback?: string;
    }>;
    profile: ApiProfile;
  }>(`/practice/submit?resource_id=${encodeURIComponent(resourceId)}`, userId, {
    method: "POST",
    body: JSON.stringify({ answers })
  });
  return {
    totalScore: data.total_score,
    results: data.results.map((r) => ({
      questionId: r.question_id,
      score: r.score,
      standardAnswer: r.standard_answer,
      gradingType: r.grading_type ?? "standard",
      feedback: r.feedback ?? ""
    })),
    profile: mapProfile(data.profile)
  };
}

export async function fetchResources(userId: string): Promise<GeneratedResource[]> {
  const rows = await request<
    Array<{
      id: string;
      type: string;
      title: string;
      summary: string;
      content: string;
      topic: string;
      created_at: string;
      player_url?: string | null;
      scene_count?: number | null;
    }>
  >("/resources", userId);
  return rows.map((r) => ({
    id: r.id,
    type: r.type as GeneratedResource["type"],
    title: r.title,
    summary: r.summary,
    content: r.content,
    topic: r.topic,
    createdAt: r.created_at,
    playerUrl: r.player_url ?? undefined,
    sceneCount: r.scene_count ?? undefined
  }));
}

function mapGeneratedResource(r: {
  id: string;
  type: string;
  title: string;
  summary: string;
  content: string;
  topic: string;
  created_at: string;
  player_url?: string | null;
  scene_count?: number | null;
}): GeneratedResource {
  return {
    id: r.id,
    type: r.type as GeneratedResource["type"],
    title: r.title,
    summary: r.summary,
    content: r.content,
    topic: r.topic,
    createdAt: r.created_at,
    playerUrl: r.player_url ?? undefined,
    sceneCount: r.scene_count ?? undefined
  };
}

export async function fetchResource(userId: string, resourceId: string): Promise<GeneratedResource> {
  const r = await request<{
    id: string;
    type: string;
    title: string;
    summary: string;
    content: string;
    topic: string;
    created_at: string;
    player_url?: string | null;
    scene_count?: number | null;
  }>(`/resources/${encodeURIComponent(resourceId)}`, userId);
  return mapGeneratedResource(r);
}

export async function deleteResource(userId: string, resourceId: string): Promise<void> {
  await request(`/resources/${encodeURIComponent(resourceId)}`, userId, { method: "DELETE" });
}

export type ResourceStudioStreamEvent =
  | {
      type: "agent_status";
      agents: Array<{ id: string; status: string; role?: string; in_hub?: boolean }>;
    }
  | {
      type: "hub_open";
      members: string[];
      topic: string;
    }
  | {
      type: "hub_close";
    }
  | {
      type: "hub";
      message: {
        id: string;
        agent: string;
        role: string;
        content: string;
        timestamp: string;
        kind?: string;
      };
    }
  | { type: "inquiry_walk" }
  | {
      type: "inquiry";
      inquiry_id: string;
      reason: string;
      questions: string[];
      requested_by?: string;
    }
  | {
      type: "agent_progress";
      agent_id: string;
      react_steps?: Array<{
        step?: number;
        thought?: string;
        action?: string;
        expert?: string;
        observation?: string;
        status?: string;
      }>;
    }
  | {
      type: "resource_stored";
      agent_id: string;
      resource: {
        id: string;
        type: string;
        title: string;
        summary: string;
        content: string;
        topic: string;
        created_at: string;
        player_url?: string | null;
        scene_count?: number | null;
      };
    }
  | {
      type: "done";
      resources: Array<{
        id: string;
        type: string;
        title: string;
        summary: string;
        content: string;
        topic: string;
        created_at: string;
        player_url?: string | null;
        scene_count?: number | null;
      }>;
    }
  | { type: "error"; message: string };

export async function generateResourcesStream(
  userId: string,
  topic: string,
  types: string[],
  onEvent: (event: ResourceStudioStreamEvent) => void,
  options?: { courseId?: string; clarification?: string }
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-User-Id": userId,
  };
  const response = await fetch(`${API_BASE}/resources/generate/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      topic,
      types,
      course_id: options?.courseId,
      clarification: options?.clarification,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API ${response.status}: /resources/generate/stream`);
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("流式响应不可用");

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let splitAt = buffer.indexOf("\n\n");
    while (splitAt !== -1) {
      const chunk = buffer.slice(0, splitAt);
      buffer = buffer.slice(splitAt + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const event = JSON.parse(line.slice(6)) as ResourceStudioStreamEvent;
        if (event.type === "error") {
          throw new Error(event.message);
        }
        onEvent(event);
      }
      splitAt = buffer.indexOf("\n\n");
    }
  }
}

export async function generateResources(
  userId: string,
  topic: string,
  types: string[],
  courseId?: string
): Promise<GeneratedResource[]> {
  const rows = await request<
    Array<{
      id: string;
      type: string;
      title: string;
      summary: string;
      content: string;
      topic: string;
      created_at: string;
      player_url?: string | null;
      scene_count?: number | null;
    }>
  >("/resources/generate", userId, {
    method: "POST",
    body: JSON.stringify({ topic, types, course_id: courseId })
  });
  return rows.map((r) => ({
    id: r.id,
    type: r.type as GeneratedResource["type"],
    title: r.title,
    summary: r.summary,
    content: r.content,
    topic: r.topic,
    createdAt: r.created_at,
    playerUrl: r.player_url ?? undefined,
    sceneCount: r.scene_count ?? undefined
  }));
}

export async function fetchLearningPath(userId: string): Promise<LearningPathStep[]> {
  const rows = await request<
    Array<{
      id: string;
      title: string;
      objective: string;
      status: string;
      estimated_minutes: number;
      resources: string[];
    }>
  >("/path", userId);
  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    objective: r.objective,
    status: r.status as LearningPathStep["status"],
    estimatedMinutes: r.estimated_minutes,
    resources: r.resources
  }));
}

export async function fetchLearningCourses(userId: string): Promise<LearningCourseSummary[]> {
  const rows = await request<
    Array<{
      id: string;
      title: string;
      topic: string;
      summary: string;
      status: string;
      module_count: number;
      progress: number;
      created_at: string;
    }>
  >("/path/courses", userId);
  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    topic: r.topic,
    summary: r.summary,
    status: r.status,
    moduleCount: r.module_count,
    progress: r.progress,
    createdAt: r.created_at
  }));
}

export async function fetchLearningCourseDetail(
  userId: string,
  courseId: string
): Promise<LearningCourseDetail> {
  const r = await request<{
    id: string;
    title: string;
    topic: string;
    summary: string;
    status: string;
    created_at: string;
    modules: Array<{
      id: string;
      title: string;
      objective: string;
      status: string;
      estimated_minutes: number;
      chapter_key: string;
      resources: Array<{ type: string; resource_id: string; title: string; order?: number; learning_order_reason?: string }>;
    }>;
  }>(`/path/courses/${encodeURIComponent(courseId)}`, userId);
  return {
    id: r.id,
    title: r.title,
    topic: r.topic,
    summary: r.summary,
    status: r.status,
    createdAt: r.created_at,
    modules: r.modules.map((m) => ({
      id: m.id,
      title: m.title,
      objective: m.objective,
      status: m.status as LearningModule["status"],
      estimatedMinutes: m.estimated_minutes,
      chapterKey: m.chapter_key,
      resources: m.resources.map(
        (res): CourseResourceRef => ({
          type: res.type,
          resourceId: res.resource_id,
          title: res.title,
          order: res.order ?? 0,
          learningOrderReason: res.learning_order_reason
        })
      )
    }))
  };
}

const RESOURCE_TYPE_ROUTE: Record<string, string> = {
  note: "/resources",
  mindmap: "/resources",
  exercise: "/practice",
  video_script: "/resources",
  code_lab: "/code-lab"
};

export function learningResourceHref(type: string, resourceId: string): string {
  const base = RESOURCE_TYPE_ROUTE[type] ?? "/resources";
  if (base === "/practice") return `${base}?resource=${encodeURIComponent(resourceId)}`;
  if (base === "/code-lab") return `${base}?resource=${encodeURIComponent(resourceId)}`;
  return `${base}?highlight=${encodeURIComponent(resourceId)}`;
}

export interface LLMConfig {
  provider: string;
  model: string;
  baseUrl: string;
  doubaoApiKeySet: boolean;
  doubaoApiKeyHint: string;
  deepseekApiKeySet: boolean;
  deepseekApiKeyHint: string;
  unlockedFamilies: string[];
  ready: boolean;
  apiKeySet: boolean;
  apiKeyHint: string;
}

type ApiLLMConfig = {
  provider: string;
  model: string;
  base_url?: string;
  doubao_api_key_set?: boolean;
  doubao_api_key_hint?: string;
  deepseek_api_key_set?: boolean;
  deepseek_api_key_hint?: string;
  unlocked_families?: string[];
  ready: boolean;
  api_key_set?: boolean;
  api_key_hint?: string;
};

function mapLLMConfig(data: ApiLLMConfig): LLMConfig {
  const unlocked = data.unlocked_families ?? [];
  return {
    provider: data.provider,
    model: data.model,
    baseUrl: data.base_url ?? "",
    doubaoApiKeySet: Boolean(data.doubao_api_key_set),
    doubaoApiKeyHint: data.doubao_api_key_hint ?? "",
    deepseekApiKeySet: Boolean(data.deepseek_api_key_set),
    deepseekApiKeyHint: data.deepseek_api_key_hint ?? "",
    unlockedFamilies: unlocked,
    ready: data.ready,
    apiKeySet: Boolean(data.api_key_set ?? (data.doubao_api_key_set || data.deepseek_api_key_set)),
    apiKeyHint: data.api_key_hint ?? data.doubao_api_key_hint ?? data.deepseek_api_key_hint ?? ""
  };
}

export async function fetchLLMConfig(userId: string): Promise<LLMConfig> {
  const data = await request<ApiLLMConfig>("/system/llm-config", userId);
  return mapLLMConfig(data);
}

export async function saveLLMConfig(
  userId: string,
  payload: {
    provider?: string;
    model?: string;
    doubao_api_key?: string;
    deepseek_api_key?: string;
  }
): Promise<LLMConfig> {
  const data = await request<ApiLLMConfig>("/system/llm-config", userId, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return mapLLMConfig(data);
}

export async function testLLMConfig(userId: string): Promise<{
  ok: boolean;
  provider: string;
  model: string;
  preview: string;
  error?: string;
}> {
  return request("/system/llm-config/test", userId, { method: "POST" });
}

export const RESOURCE_TYPE_LABELS: Record<string, string> = {
  exercise: "练习题",
  note: "笔记",
  mindmap: "思维导图",
  video_script: "讲解视频",
  code_lab: "实操案例"
};

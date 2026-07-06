const DRAFT_PREFIX = "studyverse:practice-draft";

type DraftAnswers = Record<string, string>;

function getDraftKey(userId: string, resourceId: string) {
  return `${DRAFT_PREFIX}:${userId}:${resourceId}`;
}

function isBrowserStorageAvailable() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readPracticeDraft(userId: string, resourceId: string): DraftAnswers {
  if (!userId || !resourceId || !isBrowserStorageAvailable()) return {};

  try {
    const raw = window.localStorage.getItem(getDraftKey(userId, resourceId));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};

    return Object.fromEntries(
      Object.entries(parsed).filter((entry): entry is [string, string] => typeof entry[1] === "string")
    );
  } catch {
    return {};
  }
}

export function savePracticeDraft(userId: string, resourceId: string, answers: DraftAnswers) {
  if (!userId || !resourceId || !isBrowserStorageAvailable()) return;

  const nonEmptyAnswers = Object.fromEntries(Object.entries(answers).filter(([, value]) => value.trim() !== ""));
  const key = getDraftKey(userId, resourceId);

  if (Object.keys(nonEmptyAnswers).length === 0) {
    window.localStorage.removeItem(key);
    return;
  }

  window.localStorage.setItem(key, JSON.stringify(nonEmptyAnswers));
}

export function clearPracticeDraft(userId: string, resourceId: string) {
  if (!userId || !resourceId || !isBrowserStorageAvailable()) return;
  window.localStorage.removeItem(getDraftKey(userId, resourceId));
}

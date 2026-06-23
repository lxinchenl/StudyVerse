import type { AgentStatus } from "@/lib/studio-agents";

/** LimeZu 四方向顺序：右 → 背(上) → 左 → 正(下) */
export type CharacterFacing = "right" | "up" | "left" | "down";

const IDLE_FRAME: Record<CharacterFacing, number> = {
  right: 0,
  up: 1,
  left: 2,
  down: 3,
};

const RUN_ROW: Record<CharacterFacing, number> = {
  right: 0,
  up: 1,
  left: 2,
  down: 3,
};

export interface CharacterSheetDef {
  id: string;
  /** 单帧宽（像素） */
  frameWidth: number;
  /** 单帧高（像素）；LimeZu 角色为 16×32，占 1 格宽、约 2 格高 */
  frameHeight: number;
  runFramesPerDirection: number;
  idleSrc: string;
  runSrc: string;
  /**
   * 渲染缩放。地图格 32px，角色原生高 32px，宽 16px；
   * scale=1 时身高与一格同高，scale=2 时与两格同高（偏大，一般不用）。
   */
  displayScale: number;
}

export interface CharacterSheets {
  idle: HTMLImageElement;
  run: HTMLImageElement;
}

/**
 * Modern Interiors — 四角色 idle: 64×32  run: 384×32
 * 文件名 16x16 指占地宽度，实际每帧 16×32。
 */
export const ADAM_CHARACTER: CharacterSheetDef = {
  id: "adam",
  frameWidth: 16,
  frameHeight: 32,
  runFramesPerDirection: 6,
  idleSrc: "/office/characters/Adam_idle_16x16.png",
  runSrc: "/office/characters/Adam_run_16x16.png",
  displayScale: 2,
};

export const ALEX_CHARACTER: CharacterSheetDef = {
  id: "alex",
  frameWidth: 16,
  frameHeight: 32,
  runFramesPerDirection: 6,
  idleSrc: "/office/characters/Alex_idle_16x16.png",
  runSrc: "/office/characters/Alex_run_16x16.png",
  displayScale: 2,
};

export const AMELIA_CHARACTER: CharacterSheetDef = {
  id: "amelia",
  frameWidth: 16,
  frameHeight: 32,
  runFramesPerDirection: 6,
  idleSrc: "/office/characters/Amelia_idle_16x16.png",
  runSrc: "/office/characters/Amelia_run_16x16.png",
  displayScale: 2,
};

export const BOB_CHARACTER: CharacterSheetDef = {
  id: "bob",
  frameWidth: 16,
  frameHeight: 32,
  runFramesPerDirection: 6,
  idleSrc: "/office/characters/Bob_idle_16x16.png",
  runSrc: "/office/characters/Bob_run_16x16.png",
  displayScale: 2,
};

export const OFFICE_CHARACTER_SHEETS: Record<string, CharacterSheetDef> = {
  adam: ADAM_CHARACTER,
  alex: ALEX_CHARACTER,
  amelia: AMELIA_CHARACTER,
  bob: BOB_CHARACTER,
};

/**
 * 办公室角色 → 像素形象（两个 Agent 共用一个形象）
 * - Amelia：询问员、归档员
 * - Adam：检索、笔记
 * - Alex：练习、导图
 * - Bob：视频、实操
 */
export const AGENT_OFFICE_SPRITE: Record<string, keyof typeof OFFICE_CHARACTER_SHEETS> = {
  "inquiry-desk": "amelia",
  "data-archivist": "amelia",
  "retrieval-agent": "adam",
  "note-agent": "adam",
  "exercise-agent": "alex",
  "mindmap-agent": "alex",
  "video-agent": "bob",
  "code-lab-agent": "bob",
};

export const DEFAULT_OFFICE_CHARACTER = ADAM_CHARACTER;

export function getOfficeCharacterDef(agentId: string): CharacterSheetDef {
  const spriteId = AGENT_OFFICE_SPRITE[agentId] ?? "adam";
  return OFFICE_CHARACTER_SHEETS[spriteId];
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`角色图加载失败: ${src}`));
    img.src = src;
  });
}

export async function loadCharacterSheets(def: CharacterSheetDef): Promise<CharacterSheets> {
  const [idle, run] = await Promise.all([loadImage(def.idleSrc), loadImage(def.runSrc)]);
  return { idle, run };
}

/** 预加载办公室全部 4 套形象 */
export async function loadAllOfficeCharacterSheets(): Promise<Map<string, CharacterSheets>> {
  const entries = await Promise.all(
    Object.entries(OFFICE_CHARACTER_SHEETS).map(async ([id, def]) => {
      const sheets = await loadCharacterSheets(def);
      return [id, sheets] as const;
    })
  );
  return new Map(entries);
}

/** 非工作时朝用户（正面 down），工作时朝书桌（背面 up） */
export function facingForOfficeStatus(status: AgentStatus): CharacterFacing {
  return status === "working" ? "up" : "down";
}

export function characterDisplaySize(def: CharacterSheetDef) {
  return {
    width: def.frameWidth * def.displayScale,
    height: def.frameHeight * def.displayScale,
  };
}

export function drawCharacterSprite(
  ctx: CanvasRenderingContext2D,
  sheets: CharacterSheets,
  def: CharacterSheetDef,
  facing: CharacterFacing,
  status: AgentStatus,
  tick: number,
  cx: number,
  cy: number,
  walkFrame?: number
) {
  const { frameWidth, frameHeight, runFramesPerDirection, displayScale } = def;
  const dw = frameWidth * displayScale;
  const dh = frameHeight * displayScale;
  const dx = cx - dw / 2;
  const dy = cy - dh;

  const isWalking = status === "working" && walkFrame !== undefined;

  if (status === "working") {
    const row = RUN_ROW[facing];
    const fi = isWalking
      ? walkFrame % runFramesPerDirection
      : Math.floor(tick / 5) % runFramesPerDirection;
    const sx = (row * runFramesPerDirection + fi) * frameWidth;
    ctx.drawImage(sheets.run, sx, 0, frameWidth, frameHeight, dx, dy, dw, dh);
    return;
  }

  const sx = IDLE_FRAME[facing] * frameWidth;
  ctx.drawImage(sheets.idle, sx, 0, frameWidth, frameHeight, dx, dy, dw, dh);
}

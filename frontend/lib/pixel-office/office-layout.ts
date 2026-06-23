/**
 * 办公室地图语义布局（对应 office_map.json → furniture 层）
 *
 * ┌─ 区域 ─────────────────────────────────────────────────────────────────┐
 * │ 书架（文档库）  y=1–3, x=0–11                                            │
 * │ 书桌（2×3 格）  见 DESK_TILES；占工位角色见 OFFICE_DESK_TILES             │
 * │ 地毯            y=13–15, x=4–7（装饰/走动通道，无固定工位）               │
 * └──────────────────────────────────────────────────────────────────────────┘
 *
 * 占工位角色（8）：
 *   NPC  询问员 inquiry-desk · 数据管理员 data-archivist
 *   Agent 检索 + 5 类资源生产（练习/笔记/导图/视频/实操）
 */

export const MAP_WIDTH_TILES = 30;
export const MAP_HEIGHT_TILES = 20;
export const TILE_SIZE = 32;

export interface TileRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface OfficeDeskSlot {
  id: string;
  tx: number;
  ty: number;
}

/** 书架 — furniture 层 y=1..3, x=0..11 */
export const BOOKSHELF_TILES: TileRect = { x: 0, y: 1, w: 12, h: 3 };

/** 数据管理员归档动画：书柜前站立点 */
export const BOOKSHELF_DROP_TILE = { tx: 6, ty: 4.5 };

/** 地毯 — 走动通道 */
export const CARPET_TILES: TileRect = { x: 4, y: 13, w: 4, h: 3 };

/** 2×3 书桌（格坐标） */
export const DESK_TILES: TileRect[] = [
  { x: 15, y: 3, w: 2, h: 3 },
  { x: 22, y: 3, w: 2, h: 3 },
  { x: 15, y: 6, w: 2, h: 3 },
  { x: 22, y: 6, w: 2, h: 3 },
  { x: 15, y: 10, w: 2, h: 3 },
  { x: 22, y: 10, w: 2, h: 3 },
  { x: 17, y: 14, w: 2, h: 3 },
  { x: 20, y: 14, w: 2, h: 3 },
];

export function tileRectToBounds(rect: TileRect) {
  return {
    left: rect.x / MAP_WIDTH_TILES,
    top: rect.y / MAP_HEIGHT_TILES,
    width: rect.w / MAP_WIDTH_TILES,
    height: rect.h / MAP_HEIGHT_TILES,
  };
}

export const BOOKSHELF_BOUNDS = tileRectToBounds(BOOKSHELF_TILES);
export const CARPET_BOUNDS = tileRectToBounds(CARPET_TILES);

/** 地毯正中央站立点（询问员问询用户） */
export const CARPET_CENTER_TILE = {
  tx: CARPET_TILES.x + CARPET_TILES.w / 2,
  ty: CARPET_TILES.y + CARPET_TILES.h / 2 + 0.5,
};

/** 地毯下方对话框锚点（归一化，相对地图） */
export const CARPET_DIALOG_ANCHOR = {
  left: CARPET_BOUNDS.left,
  top: CARPET_BOUNDS.top + CARPET_BOUNDS.height,
  width: CARPET_BOUNDS.width,
};

function deskStandPoint(rect: TileRect) {
  return {
    tx: rect.x + rect.w / 2,
    ty: rect.y + rect.h + 0.5,
  };
}

/**
 * 工位分配（脚底对齐站立点）
 * 朝向由状态决定：idle/waiting/done 面向用户，working 背对用户朝书桌（见 facingForOfficeStatus）
 * [0] 实操  [1] 检索  [2–5] 练习/笔记/导图/视频  [6] 询问员  [7] 数据管理员
 */
export const OFFICE_DESK_TILES: OfficeDeskSlot[] = [
  { id: "code-lab-agent", ...deskStandPoint(DESK_TILES[0]) },
  { id: "retrieval-agent", ...deskStandPoint(DESK_TILES[1]) },
  { id: "exercise-agent", ...deskStandPoint(DESK_TILES[2]) },
  { id: "note-agent", ...deskStandPoint(DESK_TILES[3]) },
  { id: "mindmap-agent", ...deskStandPoint(DESK_TILES[4]) },
  { id: "video-agent", ...deskStandPoint(DESK_TILES[5]) },
  { id: "inquiry-desk", ...deskStandPoint(DESK_TILES[6]) },
  { id: "data-archivist", ...deskStandPoint(DESK_TILES[7]) },
];

const DESK_BY_ID = new Map(OFFICE_DESK_TILES.map((d) => [d.id, d]));

export function getDeskSlot(characterId: string): OfficeDeskSlot | undefined {
  return DESK_BY_ID.get(characterId);
}

/** 走到 Agent 工位旁（略偏左，避免与 Agent 重叠） */
export function besideAgentDesk(agentId: string): { tx: number; ty: number } | null {
  const desk = getDeskSlot(agentId);
  if (!desk) return null;
  return { tx: desk.tx - 0.8, ty: desk.ty };
}

export function tileToPixel(tx: number, ty: number, tileSize = TILE_SIZE) {
  return {
    x: tx * tileSize,
    y: ty * tileSize,
  };
}

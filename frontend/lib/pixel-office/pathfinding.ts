import officeMap from "@/public/office/office_map.json";

import {
  CARPET_TILES,
  MAP_HEIGHT_TILES,
  MAP_WIDTH_TILES,
} from "./office-layout";

export interface GridCell {
  x: number;
  y: number;
}

export interface WorldPos {
  tx: number;
  ty: number;
}

const FURNITURE_LAYER = officeMap.layers.find((l) => l.name === "furniture");
const FURNITURE_DATA: number[] = FURNITURE_LAYER?.data ?? [];

const CARDINAL_DELTAS: GridCell[] = [
  { x: 1, y: 0 },
  { x: -1, y: 0 },
  { x: 0, y: 1 },
  { x: 0, y: -1 },
];

function cellKey(x: number, y: number): string {
  return `${x},${y}`;
}

function inBounds(x: number, y: number): boolean {
  return x >= 0 && y >= 0 && x < MAP_WIDTH_TILES && y < MAP_HEIGHT_TILES;
}

/** 地毯区域可站立（furniture 层有地毯贴图，但角色需走入） */
function isWalkableOverride(x: number, y: number): boolean {
  return (
    x >= CARPET_TILES.x &&
    x < CARPET_TILES.x + CARPET_TILES.w &&
    y >= CARPET_TILES.y &&
    y < CARPET_TILES.y + CARPET_TILES.h
  );
}

/** 用户标注的墙体 + furniture 非 0 格 */
export function isBlockedCell(x: number, y: number): boolean {
  if (!inBounds(x, y)) return true;
  if (isWalkableOverride(x, y)) return false;

  if (y === 0) return true;

  if (y >= 9 && y <= 10 && x >= 0 && x <= 4) return true;
  if (y >= 9 && y <= 10 && x >= 8 && x <= 12) return true;

  if (x === 13 && y >= 0 && y <= 4) return true;
  if (x === 13 && y >= 6 && y <= 16) return true;

  const idx = y * MAP_WIDTH_TILES + x;
  return (FURNITURE_DATA[idx] ?? 0) !== 0;
}

let blockedCache: Set<string> | null = null;

export function getBlockedSet(): Set<string> {
  if (blockedCache) return blockedCache;
  const set = new Set<string>();
  for (let y = 0; y < MAP_HEIGHT_TILES; y++) {
    for (let x = 0; x < MAP_WIDTH_TILES; x++) {
      if (isBlockedCell(x, y)) set.add(cellKey(x, y));
    }
  }
  blockedCache = set;
  return set;
}

export function worldToCell(pos: WorldPos): GridCell {
  return { x: Math.floor(pos.tx), y: Math.floor(pos.ty) };
}

export function cellToWorld(cell: GridCell): WorldPos {
  return { tx: cell.x + 0.5, ty: cell.y + 0.5 };
}

/** 将任意世界坐标吸附到最近可行走格 */
export function nearestWalkableCell(
  cell: GridCell,
  blocked: Set<string> = getBlockedSet(),
  maxRadius = 12
): GridCell | null {
  if (!blocked.has(cellKey(cell.x, cell.y))) return cell;

  const queue: GridCell[] = [cell];
  const seen = new Set<string>([cellKey(cell.x, cell.y)]);

  while (queue.length > 0) {
    const cur = queue.shift()!;
    if (
      Math.abs(cur.x - cell.x) + Math.abs(cur.y - cell.y) > maxRadius
    ) {
      continue;
    }
    if (!blocked.has(cellKey(cur.x, cur.y))) return cur;

    for (const d of CARDINAL_DELTAS) {
      const nx = cur.x + d.x;
      const ny = cur.y + d.y;
      const k = cellKey(nx, ny);
      if (!inBounds(nx, ny) || seen.has(k)) continue;
      seen.add(k);
      queue.push({ x: nx, y: ny });
    }
  }
  return null;
}

/**
 * 四向 BFS 最短路（无权图，等价于 Dijkstra）
 * 返回包含起点与终点的格子序列
 */
export function findGridPath(
  start: GridCell,
  goal: GridCell,
  blocked: Set<string> = getBlockedSet()
): GridCell[] {
  const startK = cellKey(start.x, start.y);
  const goalK = cellKey(goal.x, goal.y);

  if (startK === goalK) return [start];
  if (blocked.has(startK) || blocked.has(goalK)) return [];

  const queue: GridCell[] = [start];
  const cameFrom = new Map<string, string>();
  const visited = new Set<string>([startK]);

  while (queue.length > 0) {
    const cur = queue.shift()!;
    const curK = cellKey(cur.x, cur.y);

    if (curK === goalK) {
      const path: GridCell[] = [];
      let k: string | undefined = goalK;
      while (k) {
        const [xs, ys] = k.split(",");
        path.push({ x: Number(xs), y: Number(ys) });
        k = cameFrom.get(k);
      }
      return path.reverse();
    }

    for (const d of CARDINAL_DELTAS) {
      const nx = cur.x + d.x;
      const ny = cur.y + d.y;
      const nk = cellKey(nx, ny);
      if (!inBounds(nx, ny) || blocked.has(nk) || visited.has(nk)) continue;
      visited.add(nk);
      cameFrom.set(nk, curK);
      queue.push({ x: nx, y: ny });
    }
  }

  return [];
}

export function findWalkPath(
  from: WorldPos,
  to: WorldPos,
  blocked: Set<string> = getBlockedSet()
): WorldPos[] {
  const startCell = nearestWalkableCell(worldToCell(from), blocked);
  const goalCell = nearestWalkableCell(worldToCell(to), blocked);
  if (!startCell || !goalCell) return [from, to];

  const grid = findGridPath(startCell, goalCell, blocked);
  if (grid.length === 0) return [from, to];

  return grid.map(cellToWorld);
}

/** 串联多段锚点，每段独立寻路，仅上下左右移动 */
export function buildWalkRoute(
  anchors: WorldPos[],
  blocked: Set<string> = getBlockedSet()
): WorldPos[] {
  if (anchors.length === 0) return [];
  if (anchors.length === 1) return [...anchors];

  const route: WorldPos[] = [];
  for (let i = 0; i < anchors.length - 1; i++) {
    const leg = findWalkPath(anchors[i], anchors[i + 1], blocked);
    if (leg.length === 0) continue;
    if (route.length > 0) {
      const last = route[route.length - 1];
      const first = leg[0];
      if (last.tx === first.tx && last.ty === first.ty) {
        route.push(...leg.slice(1));
        continue;
      }
    }
    route.push(...leg);
  }

  return route.length > 0 ? route : [...anchors];
}

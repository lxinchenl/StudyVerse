import type { CharacterFacing } from "./characters";
import { buildWalkRoute, type WorldPos } from "./pathfinding";

export interface WalkerState {
  waypoints: WorldPos[];
  segIndex: number;
  segProgress: number;
  /** 每帧移动的图块距离（仅沿上下左右） */
  speed: number;
  /** 行走动画帧计数（每 stepWalker 递增） */
  animTick: number;
}

export function facingFromDelta(dx: number, dy: number): CharacterFacing {
  if (dx > 0) return "right";
  if (dx < 0) return "left";
  if (dy > 0) return "down";
  if (dy < 0) return "up";
  return "down";
}

/**
 * 创建沿网格路径的行走器（四向、避障路径由 pathfinding 预计算）
 */
export function createWalker(anchors: WorldPos[], speed = 0.1): WalkerState {
  const waypoints = buildWalkRoute(anchors);
  if (waypoints.length < 2) {
    const p = waypoints[0] ?? anchors[0] ?? { tx: 0, ty: 0 };
    return { waypoints: [p, { ...p }], segIndex: 0, segProgress: 0, speed, animTick: 0 };
  }
  return { waypoints, segIndex: 0, segProgress: 0, speed, animTick: 0 };
}

const WALK_ANIM_FRAME_DIVISOR = 4;

export function stepWalker(state: WalkerState): {
  done: boolean;
  tx: number;
  ty: number;
  facing: CharacterFacing;
  animFrame: number;
} {
  const from = state.waypoints[state.segIndex];
  const to = state.waypoints[state.segIndex + 1];

  if (!from || !to) {
    const last = state.waypoints[state.waypoints.length - 1];
    return {
      done: true,
      tx: last.tx,
      ty: last.ty,
      facing: "down",
      animFrame: 0,
    };
  }

  const dx = to.tx - from.tx;
  const dy = to.ty - from.ty;
  const segLen = Math.abs(dx) + Math.abs(dy);

  if (segLen < 1e-6) {
    state.segIndex += 1;
    state.segProgress = 0;
    if (state.segIndex >= state.waypoints.length - 1) {
      return { done: true, tx: to.tx, ty: to.ty, facing: "down", animFrame: 0 };
    }
    return stepWalker(state);
  }

  const facing = facingFromDelta(dx, dy);

  state.segProgress += state.speed;
  if (state.segProgress >= segLen) {
    state.segIndex += 1;
    state.segProgress = 0;
    if (state.segIndex >= state.waypoints.length - 1) {
      return { done: true, tx: to.tx, ty: to.ty, facing, animFrame: 0 };
    }
    return stepWalker(state);
  }

  state.animTick += 1;
  const animFrame = Math.floor(state.animTick / WALK_ANIM_FRAME_DIVISOR) % 6;

  const t = state.segProgress / segLen;
  return {
    done: false,
    tx: from.tx + dx * t,
    ty: from.ty + dy * t,
    facing,
    animFrame,
  };
}

import {
  BOOKSHELF_DROP_TILE,
  besideAgentDesk,
  getDeskSlot,
} from "./office-layout";
import { createWalker, type WalkerState } from "./walker";

export interface ArchivistTrip {
  id: string;
  /** 按生成顺序，逐一拜访的生产 Agent */
  agentIds: string[];
}

function archivistHome() {
  const desk = getDeskSlot("data-archivist");
  if (!desk) return BOOKSHELF_DROP_TILE;
  return { tx: desk.tx, ty: desk.ty };
}

/**
 * 工位 → 各生产 Agent 旁（按顺序）→ 书柜 → 回工位
 */
export function createArchivistWalker(trip: ArchivistTrip): WalkerState {
  const home = archivistHome();
  const anchors = [home];

  for (const agentId of trip.agentIds) {
    const beside = besideAgentDesk(agentId);
    if (beside) anchors.push(beside);
  }

  anchors.push(BOOKSHELF_DROP_TILE, home);
  return createWalker(anchors, 0.08);
}

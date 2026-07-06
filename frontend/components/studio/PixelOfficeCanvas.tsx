"use client";

import { memo, useEffect, useRef, useState } from "react";

import {
  characterDisplaySize,
  drawCharacterSprite,
  facingForOfficeStatus,
  getOfficeCharacterDef,
  loadAllOfficeCharacterSheets,
  type CharacterFacing,
  type CharacterSheets,
} from "@/lib/pixel-office/characters";
import { createArchivistWalker, type ArchivistTrip } from "@/lib/pixel-office/archivist";
import {
  BOOKSHELF_BOUNDS,
  CARPET_CENTER_TILE,
  CARPET_DIALOG_ANCHOR,
  getDeskSlot,
  OFFICE_DESK_TILES,
  tileToPixel,
} from "@/lib/pixel-office/office-layout";
import { createWalker, stepWalker, type WalkerState } from "@/lib/pixel-office/walker";
import {
  drawTiledLayer,
  loadTiledImages,
  mapPixelSize,
  parseTiledMap,
  type TiledMap,
} from "@/lib/pixel-office/tiled";
import { getAgentMeta, OFFICE_CHARACTERS, type AgentStatus } from "@/lib/studio-agents";
import type { AgentState } from "./AgentWorkbench";
import { CarpetInquiryPanel } from "./CarpetInquiryPanel";

const MAP_URL = "/office/office_map.json";

export type InquiryFlowPhase = "walk_to_carpet" | "at_carpet" | "walk_home" | null;

interface PixelOfficeCanvasProps {
  agents: AgentState[];
  bubbles: Record<string, string>;
  activeSpeaker?: string | null;
  onBookshelfClick?: () => void;
  inquiryPhase?: InquiryFlowPhase;
  inquiryData?: { reason: string; questions: string[] } | null;
  inquiryDraft?: string;
  onInquiryDraftChange?: (v: string) => void;
  onInquirySubmit?: () => void;
  onInquiryArrived?: () => void;
  onInquiryHome?: () => void;
  archivistTrips?: ArchivistTrip[];
  onArchivistTripComplete?: (tripId: string) => void;
}

interface CharacterPose {
  tx: number;
  ty: number;
  facing: CharacterFacing;
  status: AgentStatus;
  walkFrame?: number;
}

function drawRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function PixelOfficeCanvasInner({
  agents,
  bubbles,
  activeSpeaker,
  onBookshelfClick,
  inquiryPhase = null,
  inquiryData,
  inquiryDraft = "",
  onInquiryDraftChange,
  onInquirySubmit,
  onInquiryArrived,
  onInquiryHome,
  archivistTrips = [],
  onArchivistTripComplete,
}: PixelOfficeCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const agentsRef = useRef(agents);
  const bubblesRef = useRef(bubbles);
  const speakerRef = useRef(activeSpeaker);
  const inquiryPhaseRef = useRef(inquiryPhase);
  const archivistTripsRef = useRef(archivistTrips);
  const tickRef = useRef(0);
  const rafRef = useRef(0);
  const mapRef = useRef<TiledMap | null>(null);
  const tileImagesRef = useRef<Map<string, HTMLImageElement> | null>(null);
  const characterSheetsRef = useRef<Map<string, CharacterSheets> | null>(null);
  const inquiryWalkerRef = useRef<WalkerState | null>(null);
  const archivistWalkerRef = useRef<WalkerState | null>(null);
  const currentArchivistTripRef = useRef<string | null>(null);
  const poseOverridesRef = useRef<Record<string, CharacterPose>>({});
  const bubbleLayerRef = useRef<HTMLDivElement>(null);
  const bookshelfHighlightRef = useRef(false);
  const onInquiryArrivedRef = useRef(onInquiryArrived);
  const onInquiryHomeRef = useRef(onInquiryHome);
  const onArchivistTripCompleteRef = useRef(onArchivistTripComplete);
  const [loadError, setLoadError] = useState("");
  const [sceneReady, setSceneReady] = useState(false);
  const [showCarpetDialog, setShowCarpetDialog] = useState(false);

  agentsRef.current = agents;
  bubblesRef.current = bubbles;
  speakerRef.current = activeSpeaker;
  inquiryPhaseRef.current = inquiryPhase;
  archivistTripsRef.current = archivistTrips;
  onInquiryArrivedRef.current = onInquiryArrived;
  onInquiryHomeRef.current = onInquiryHome;
  onArchivistTripCompleteRef.current = onArchivistTripComplete;

  useEffect(() => {
    if (inquiryPhase === "at_carpet") {
      setShowCarpetDialog(true);
    } else if (!inquiryPhase) {
      setShowCarpetDialog(false);
    }
  }, [inquiryPhase]);

  useEffect(() => {
    if (inquiryPhase === "walk_to_carpet") {
      const home = getDeskSlot("inquiry-desk");
      if (home) {
        inquiryWalkerRef.current = createWalker(
          [{ tx: home.tx, ty: home.ty }, CARPET_CENTER_TILE],
          0.1
        );
      }
    } else if (inquiryPhase === "walk_home") {
      const home = getDeskSlot("inquiry-desk");
      if (home) {
        inquiryWalkerRef.current = createWalker(
          [CARPET_CENTER_TILE, { tx: home.tx, ty: home.ty }],
          0.1
        );
      }
    } else if (!inquiryPhase) {
      inquiryWalkerRef.current = null;
    }
  }, [inquiryPhase]);

  useEffect(() => {
    let cancelled = false;

    async function loadScene() {
      try {
        const [mapRes, sheets] = await Promise.all([
          fetch(MAP_URL).then(async (res) => {
            if (!res.ok) throw new Error(`地图加载失败 (${res.status})`);
            return res.json() as Promise<TiledMap>;
          }),
          loadAllOfficeCharacterSheets(),
        ]);

        const map = parseTiledMap(mapRes);
        const tileImages = await loadTiledImages(map.tilesets);
        if (cancelled) return;

        mapRef.current = map;
        tileImagesRef.current = tileImages;
        characterSheetsRef.current = sheets;
        setSceneReady(true);
        setLoadError("");
      } catch (e) {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : "场景加载失败");
        }
      }
    }

    loadScene();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const agentMap = () => new Map(agentsRef.current.map((a) => [a.id, a]));

    let lastDisplayW = 0;
    let lastDisplayH = 0;

    function fitCanvas() {
      const map = mapRef.current;
      if (!map) return;

      const { width: mapW, height: mapH } = mapPixelSize(map);
      // Use "cover" scaling so the office fills the scene area width/height
      // instead of shrinking to a small centered thumbnail.
      const scale = Math.max(wrap!.clientWidth / mapW, wrap!.clientHeight / mapH);
      const displayW = Math.max(1, Math.floor(mapW * scale));
      const displayH = Math.max(1, Math.floor(mapH * scale));

      if (displayW === lastDisplayW && displayH === lastDisplayH) return;
      lastDisplayW = displayW;
      lastDisplayH = displayH;

      canvas!.width = mapW;
      canvas!.height = mapH;
      canvas!.style.width = `${displayW}px`;
      canvas!.style.height = `${displayH}px`;
      if (stageRef.current) {
        stageRef.current.style.width = `${displayW}px`;
        stageRef.current.style.height = `${displayH}px`;
      }
    }

    function updateSpeechBubbles(map: TiledMap, mapAgents: Map<string, AgentState>) {
      const layer = bubbleLayerRef.current;
      if (!layer) return;

      const { width: mapW, height: mapH } = mapPixelSize(map);
      const { tilewidth } = map;

      for (const desk of OFFICE_DESK_TILES) {
        const el = layer.querySelector<HTMLElement>(`[data-desk="${desk.id}"]`);
        if (!el) continue;

        const agent = mapAgents.get(desk.id) ?? { id: desk.id, status: "idle" as AgentStatus };
        const bubble = bubblesRef.current[desk.id];
        const isInactive = agent.status === "inactive";

        if (!bubble || isInactive) {
          el.hidden = true;
          continue;
        }

        const pose = resolvePose(desk.id, agent);
        const { x: cx, y: cy } = tileToPixel(pose.tx, pose.ty, tilewidth);
        const charDef = getOfficeCharacterDef(desk.id);
        const spriteTop = cy - characterDisplaySize(charDef).height;
        const emphasize = speakerRef.current === desk.id;
        const text = bubble.length > 52 ? `${bubble.slice(0, 52)}…` : bubble;

        el.hidden = false;
        el.textContent = text;
        el.classList.toggle("emphasize", emphasize);
        el.style.left = `${(cx / mapW) * 100}%`;
        el.style.top = `${(Math.max(4, spriteTop - 8) / mapH) * 100}%`;
      }
    }

    function drawBookshelfHighlight(map: TiledMap) {
      if (!bookshelfHighlightRef.current) return;
      const { tilewidth, tileheight } = map;
      const x = BOOKSHELF_BOUNDS.left * map.width * tilewidth;
      const y = BOOKSHELF_BOUNDS.top * map.height * tileheight;
      const w = BOOKSHELF_BOUNDS.width * map.width * tilewidth;
      const h = BOOKSHELF_BOUNDS.height * map.height * tileheight;
      ctx!.fillStyle = "rgba(0, 82, 217, 0.12)";
      ctx!.fillRect(x, y, w, h);
      ctx!.strokeStyle = "rgba(0, 82, 217, 0.5)";
      ctx!.lineWidth = 2;
      ctx!.strokeRect(x + 1, y + 1, w - 2, h - 2);
    }

    function updateWalkers() {
      const overrides: Record<string, CharacterPose> = {};
      const phase = inquiryPhaseRef.current;

      if (inquiryWalkerRef.current && phase) {
        const step = stepWalker(inquiryWalkerRef.current);
        const status: AgentStatus = step.done ? "waiting" : "working";
        overrides["inquiry-desk"] = {
          tx: step.tx,
          ty: step.ty,
          facing: step.done && phase === "at_carpet" ? "down" : step.facing,
          status,
          walkFrame: step.done ? undefined : step.animFrame,
        };
        if (step.done && phase === "walk_to_carpet") {
          inquiryWalkerRef.current = null;
          onInquiryArrivedRef.current?.();
        }
        if (step.done && phase === "walk_home") {
          inquiryWalkerRef.current = null;
          onInquiryHomeRef.current?.();
        }
      } else if (phase === "at_carpet") {
        overrides["inquiry-desk"] = {
          tx: CARPET_CENTER_TILE.tx,
          ty: CARPET_CENTER_TILE.ty,
          facing: "down",
          status: "waiting",
        };
      }

      if (!archivistWalkerRef.current && archivistTripsRef.current.length > 0) {
        const trip = archivistTripsRef.current[0];
        currentArchivistTripRef.current = trip.id;
        archivistWalkerRef.current = createArchivistWalker(trip);
      }

      if (archivistWalkerRef.current) {
        const step = stepWalker(archivistWalkerRef.current);
        overrides["data-archivist"] = {
          tx: step.tx,
          ty: step.ty,
          facing: step.facing,
          status: step.done ? "idle" : "working",
          walkFrame: step.done ? undefined : step.animFrame,
        };
        if (step.done) {
          archivistWalkerRef.current = null;
          const tripId = currentArchivistTripRef.current;
          currentArchivistTripRef.current = null;
          if (tripId) onArchivistTripCompleteRef.current?.(tripId);
        }
      }

      poseOverridesRef.current = overrides;
    }

    function resolvePose(deskId: string, agent: AgentState): CharacterPose {
      const override = poseOverridesRef.current[deskId];
      if (override) return override;
      const desk = getDeskSlot(deskId);
      if (!desk) {
        return { tx: 0, ty: 0, facing: "down", status: agent.status };
      }
      return {
        tx: desk.tx,
        ty: desk.ty,
        facing: facingForOfficeStatus(agent.status),
        status: agent.status,
      };
    }

    function loop() {
      tickRef.current += 1;
      const map = mapRef.current;
      const tileImages = tileImagesRef.current;
      const characterSheetsMap = characterSheetsRef.current;
      if (!map || !tileImages || !characterSheetsMap) {
        rafRef.current = requestAnimationFrame(loop);
        return;
      }

      updateWalkers();
      ctx!.imageSmoothingEnabled = false;
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height);

      for (const layer of map.layers) {
        drawTiledLayer(ctx!, layer, map, tileImages);
      }

      drawBookshelfHighlight(map);

      const mapAgents = agentMap();
      const { tilewidth } = map;

      for (const desk of OFFICE_DESK_TILES) {
        const agent = mapAgents.get(desk.id) ?? { id: desk.id, status: "idle" as AgentStatus };
        const pose = resolvePose(desk.id, agent);
        const { x: cx, y: cy } = tileToPixel(pose.tx, pose.ty, tilewidth);
        const meta = getAgentMeta(desk.id);
        const charDef = getOfficeCharacterDef(desk.id);
        const characterSheets = characterSheetsMap.get(charDef.id);
        if (!characterSheets) continue;

        const isInactive = agent.status === "inactive";
        const isWalking = pose.walkFrame !== undefined;
        const animStatus = isWalking
          ? "working"
          : pose.status === "waiting" || isInactive
            ? "idle"
            : pose.status;
        const facing = isInactive ? "down" : pose.facing;

        drawCharacterSprite(
          ctx!,
          characterSheets,
          charDef,
          facing,
          animStatus,
          tickRef.current,
          cx,
          cy,
          pose.walkFrame
        );

        ctx!.font = "600 10px sans-serif";
        ctx!.textAlign = "center";
        ctx!.textBaseline = "middle";
        const label = meta.shortName;
        const metrics = ctx!.measureText(label);
        const labelW = Math.ceil(metrics.width) + 10;
        const labelH = 16;
        const labelX = cx - labelW / 2;
        const labelY = cy + 6;
        drawRoundRect(ctx!, labelX, labelY, labelW, labelH, 6);
        ctx!.fillStyle = "rgba(255, 255, 255, 0.92)";
        ctx!.fill();
        ctx!.strokeStyle = agent.status === "inactive" ? "rgba(134, 144, 156, 0.35)" : "rgba(29, 33, 41, 0.14)";
        ctx!.lineWidth = 1;
        ctx!.stroke();
        ctx!.fillStyle = agent.status === "inactive" ? "#667085" : "#1d2129";
        ctx!.fillText(label, cx, labelY + labelH / 2);
      }

      updateSpeechBubbles(map, mapAgents);

      rafRef.current = requestAnimationFrame(loop);
    }

    const ro = new ResizeObserver(() => fitCanvas());
    ro.observe(wrap);
    fitCanvas();
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [sceneReady]);

  return (
    <div ref={wrapRef} className="pixel-office-wrap">
      <div ref={stageRef} className="pixel-office-stage">
        <canvas
          ref={canvasRef}
          className="pixel-office-canvas"
          aria-label="像素办公室"
        />
        <div ref={bubbleLayerRef} className="pixel-office-bubble-layer" aria-hidden>
          {OFFICE_DESK_TILES.map((desk) => (
            <div key={desk.id} className="pixel-office-speech-bubble" data-desk={desk.id} hidden />
          ))}
        </div>
        {showCarpetDialog && inquiryData ? (
          <div
            className="carpet-inquiry-anchor"
            style={{
              left: `${CARPET_DIALOG_ANCHOR.left * 100}%`,
              top: `${CARPET_DIALOG_ANCHOR.top * 100}%`,
              width: `${CARPET_DIALOG_ANCHOR.width * 100}%`,
            }}
          >
            <CarpetInquiryPanel
              reason={inquiryData.reason}
              questions={inquiryData.questions}
              value={inquiryDraft}
              onChange={(v) => onInquiryDraftChange?.(v)}
              onSubmit={() => onInquirySubmit?.()}
            />
          </div>
        ) : null}
        {onBookshelfClick && sceneReady ? (
          <button
            type="button"
            className="office-bookshelf-hit"
            style={{
              left: `${BOOKSHELF_BOUNDS.left * 100}%`,
              top: `${BOOKSHELF_BOUNDS.top * 100}%`,
              width: `${BOOKSHELF_BOUNDS.width * 100}%`,
              height: `${BOOKSHELF_BOUNDS.height * 100}%`,
            }}
            aria-label="打开文档库"
            title="文档库 — 查看已生成资源"
            onClick={onBookshelfClick}
            onMouseEnter={() => {
              bookshelfHighlightRef.current = true;
            }}
            onMouseLeave={() => {
              bookshelfHighlightRef.current = false;
            }}
          >
            <span className="office-bookshelf-hit-label">文档库</span>
          </button>
        ) : null}
      </div>
      {loadError ? <p className="pixel-office-load-error">{loadError}</p> : null}
      {!sceneReady && !loadError ? <p className="pixel-office-loading">加载办公室场景…</p> : null}
    </div>
  );
}

export const PixelOfficeCanvas = memo(PixelOfficeCanvasInner);

export const OFFICE_DESK_IDS = OFFICE_DESK_TILES.map((d) => d.id);

export function defaultOfficeAgents(): AgentState[] {
  return OFFICE_CHARACTERS.map((a) => ({
    id: a.id,
    status: "idle" as AgentStatus,
    role: a.role,
  }));
}

export { BOOKSHELF_BOUNDS };

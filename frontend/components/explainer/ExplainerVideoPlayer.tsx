"use client";

import { API_BASE } from "@/lib/constants";
import type { ExplainerVideo } from "@/lib/types";

export function explainerPlayerUrl(playerUrl: string): string {
  const join = (base: string, query: string) =>
    base.includes("?") ? `${base}&${query}` : `${base}?${query}`;
  if (playerUrl.startsWith("http")) return join(playerUrl, "embed=1");
  const origin = API_BASE.replace(/\/api$/, "");
  const path = playerUrl.startsWith("/") ? playerUrl : `/${playerUrl}`;
  return join(`${origin}${path}`, "embed=1");
}

export function ExplainerVideoPlayer({
  video,
  compact = false
}: {
  video: ExplainerVideo;
  compact?: boolean;
}) {
  const src = explainerPlayerUrl(video.playerUrl);

  return (
    <div className={`explainer-player${compact ? " explainer-player-compact" : ""}`}>
      <div className="explainer-player-head">
        <strong>{video.title}</strong>
        {video.sceneCount ? (
          <span className="muted">{video.sceneCount} 镜 · HTML 讲解</span>
        ) : null}
      </div>
      <div className="explainer-player-frame-wrap">
        <iframe
          title={video.title}
          src={src}
          className="explainer-player-frame"
          allow="fullscreen"
          loading="lazy"
        />
      </div>
      {video.summary ? <p className="muted explainer-player-summary">{video.summary}</p> : null}
    </div>
  );
}

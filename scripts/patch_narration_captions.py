"""One-off: inject in-frame narration captions into explainer HTML."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/generated_resources/explainer/explainer-a74779bd6e"

CAPTION_CSS = """
    /* --- 画面内配音字幕（手动预览） --- */
    .narration-caption {
      position: absolute;
      left: 12px;
      right: 12px;
      bottom: 10px;
      padding: 14px 18px;
      background: rgba(15, 23, 42, 0.92);
      color: #f8fafc;
      font-size: clamp(0.92rem, 1.55vw, 1.12rem);
      line-height: 1.65;
      border-radius: 12px;
      border-left: 4px solid #38bdf8;
      box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
      z-index: 12;
      text-align: left;
    }
    .narration-caption.speaking {
      border-left-color: #fbbf24;
      background: rgba(15, 23, 42, 0.97);
      box-shadow: 0 12px 32px rgba(56, 189, 248, 0.18);
    }
    .scene-relative {
      position: relative;
      width: min(1080px, 96%);
      padding-bottom: 88px;
    }
    .scene-content {
      padding-bottom: 88px;
    }
    .subtitle-bar { display: none !important; }
"""


def main() -> None:
    page_path = BUNDLE / "index.html"
    sb_path = BUNDLE / "storyboard.json"
    page = page_path.read_text(encoding="utf-8")
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    narrations = [str(scene.get("narration") or "").strip() for scene in sb["scenes"]]

    if ".narration-caption" not in page:
        page = page.replace(".subtitle-bar.speaking {", CAPTION_CSS + "\n    .subtitle-bar.speaking {")

    page = re.sub(
        r'function setSpeakingVisual\(active\) \{\s*scenes\.forEach\(\(scene, i\) => \{\s*const bar = scene\.querySelector\("\.subtitle-bar"\);\s*if \(bar\) bar\.classList\.toggle\("speaking", active && i === current\);\s*\}\);\s*\}',
        """function setSpeakingVisual(active) {
      scenes.forEach((scene, i) => {
        const on = active && i === current;
        scene.querySelectorAll(".subtitle-bar, .narration-caption").forEach((el) => {
          el.classList.toggle("speaking", on);
        });
      });
    }""",
        page,
        count=1,
    )

    for i, text in enumerate(narrations):
        cap = f'<div class="narration-caption">{html.escape(text)}</div>'
        if i == 0:
            marker = '<section class="scene active" data-index="0">'
            start = page.find(marker)
            if start == -1:
                raise SystemExit("scene 0 not found")
            end = page.find("</section>", start)
            block = page[start:end]
            if "narration-caption" in block:
                block = re.sub(
                    r'<div class="narration-caption">.*?</div>',
                    cap,
                    block,
                    count=1,
                    flags=re.S,
                )
            else:
                block = block.replace(
                    '<div class="title-card">',
                    '<div class="scene-relative"><div class="title-card">',
                    1,
                )
                block = block.replace(
                    "</span></div><div class=\"subtitle-bar\">",
                    f"</span></div>{cap}</div><div class=\"subtitle-bar\">",
                    1,
                )
            page = page[:start] + block + page[end:]
            continue

        pattern = (
            rf'(<section class="scene" data-index="{i}"><div class="scene-content">)'
            rf'(.*?)'
            rf'(<div class="subtitle-bar">.*?</div></section>)'
        )
        match = re.search(pattern, page, flags=re.S)
        if not match:
            raise SystemExit(f"scene {i} not found")
        inner = match.group(2)
        if "narration-caption" in inner:
            inner = re.sub(
                r'<div class="narration-caption">.*?</div>',
                cap,
                inner,
                count=1,
                flags=re.S,
            )
        else:
            inner = inner.rstrip() + cap
        replacement = match.group(1) + inner + match.group(3)
        page = page[: match.start()] + replacement + page[match.end() :]

    page_path.write_text(page, encoding="utf-8")
    print(f"Patched {page_path}")


if __name__ == "__main__":
    main()

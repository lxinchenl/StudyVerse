"""Render storyboard JSON into explainer HTML (HTML + local audio method)."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
DEMO_HTML = ROOT / "demo" / "2nf-animation.html"

NARRATION_CAPTION_CSS = """
    .narration-caption {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 16px;
      padding: 0 clamp(20px, 3vw, 48px);
      background: none;
      color: #0f172a;
      font-size: clamp(1.84rem, 3.1vw, 2.24rem);
      line-height: 1.5;
      border: none;
      box-shadow: none;
      z-index: 12;
      text-align: center;
    }
    .narration-caption.speaking {
      color: #0369a1;
      font-weight: 600;
    }
    .subtitle-bar { display: none !important; }
"""


def _esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _normalize_col_map(value: Any) -> dict[str, str]:
    """Accept column_tags/column_styles as dict or list (LLM output varies)."""
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if v is not None and str(v).strip()}
    if isinstance(value, list):
        return {
            str(i): str(v)
            for i, v in enumerate(value)
            if v is not None and str(v).strip()
        }
    return {}


def _normalize_dep_node(value: Any, *, default_style: str = "primary") -> dict[str, str]:
    """Accept diagram node as dict or plain string label."""
    if isinstance(value, dict):
        return {
            "label": str(value.get("label") or value.get("text") or ""),
            "hint": str(value.get("hint") or ""),
            "style": str(value.get("style") or default_style),
        }
    if value is None:
        return {"label": "", "hint": "", "style": default_style}
    return {"label": str(value), "hint": "", "style": default_style}


def _normalize_badge(value: Any) -> dict[str, str] | None:
    if not value:
        return None
    if isinstance(value, dict):
        return {
            "style": str(value.get("style") or "warn"),
            "text": str(value.get("text") or value.get("label") or ""),
        }
    text = str(value).strip()
    if text in ("warn", "ok", "success", "danger"):
        style = "ok" if text in ("ok", "success") else "warn" if text == "warn" else text
        return {"style": style, "text": ""}
    return {"style": "warn", "text": text}


def _normalize_title_card_props(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "heading": (
            props.get("heading")
            or props.get("title")
            or props.get("main_title")
            or props.get("mainTitle")
            or ""
        ),
        "tag": (
            props.get("tag")
            or props.get("subtitle")
            or props.get("sub_title")
            or props.get("subTitle")
            or ""
        ),
    }


def _normalize_data_table_props(props: dict[str, Any]) -> dict[str, Any]:
    columns = props.get("columns") or props.get("table_header") or props.get("headers") or []
    rows = props.get("rows") or props.get("table_rows") or []
    return {**props, "columns": columns, "rows": rows}


def _normalize_step_panel_props(props: dict[str, Any]) -> dict[str, Any]:
    steps_out: list[dict[str, Any]] = []
    for step in props.get("steps") or []:
        if not isinstance(step, dict):
            continue
        chips_raw = step.get("chips")
        chips: list[str] = []
        title_from_chips = ""
        if isinstance(chips_raw, str) and chips_raw.strip():
            title_from_chips = chips_raw.strip()
        elif isinstance(chips_raw, list):
            chips = [str(c).strip() for c in chips_raw if c is not None and str(c).strip()]
        elif step.get("chip"):
            chips = [str(step["chip"]).strip()]

        steps_out.append(
            {
                "title": (
                    step.get("title")
                    or step.get("name")
                    or title_from_chips
                    or step.get("chip")
                    or ""
                ),
                "body": (
                    step.get("body")
                    or step.get("content")
                    or step.get("desc")
                    or step.get("description")
                    or ""
                ),
                "chips": chips,
                "compare": step.get("compare"),
            }
        )
    return {
        "heading": props.get("heading") or props.get("title") or props.get("main_title") or "",
        "lead": props.get("lead") or props.get("subtitle") or props.get("sub_title") or "",
        "steps": steps_out,
    }


def _normalize_split_table(table: dict[str, Any]) -> dict[str, Any]:
    entry = dict(table)
    if not entry.get("columns"):
        entry["columns"] = entry.get("header") or entry.get("table_header") or []
    if not entry.get("rows"):
        entry["rows"] = entry.get("table_rows") or []
    return entry


def _normalize_split_tables_props(props: dict[str, Any]) -> dict[str, Any]:
    if props.get("tables"):
        tables = [_normalize_split_table(t) for t in props["tables"] if isinstance(t, dict)]
        return {**props, "tables": tables}
    tables: list[dict[str, Any]] = []
    for side in ("left", "right", "center"):
        table = props.get(f"{side}_table")
        if not isinstance(table, dict):
            continue
        entry = _normalize_split_table(table)
        entry["title"] = props.get(f"{side}_title") or table.get("title") or ""
        tables.append(entry)
    return {**props, "tables": tables}


def _normalize_summary_item(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("text") or value.get("content") or value.get("label") or ""
        ).strip()
    return str(value if value is not None else "").strip()


def _render_dep_diagram(diagram: Any) -> str:
    if not diagram or not isinstance(diagram, dict):
        return ""
    rows_html: list[str] = []
    for row in diagram.get("rows") or []:
        if not isinstance(row, dict):
            continue
        frm = _normalize_dep_node(row.get("from"))
        to = _normalize_dep_node(row.get("to"))
        arrow_style = row.get("arrow_style") or frm.get("style") or "primary"
        if arrow_style in ("danger", "warn"):
            arrow_class = "warn"
        elif arrow_style == "success":
            arrow_class = "success"
        else:
            arrow_class = ""
        badge_html = ""
        badge = _normalize_badge(row.get("badge"))
        if badge:
            badge_html = (
                f'<span class="badge {_esc(badge.get("style", "warn"))}">'
                f'{_esc(badge.get("text", ""))}</span>'
            )
        rows_html.append(
            f'<div class="dep-row" style="margin-bottom:14px;">'
            f'<div class="dep-node {_esc(frm.get("style", "primary"))}">'
            f'{_esc(frm.get("label", ""))}<small>{_esc(frm.get("hint", ""))}</small></div>'
            f'<div class="dep-arrow {arrow_class}"><span>{_esc(row.get("arrow_label", "→"))}</span>'
            f'<div class="dep-arrow-line"></div></div>'
            f'<div class="dep-node {_esc(to.get("style", "primary"))}">'
            f'{_esc(to.get("label", ""))}<small>{_esc(to.get("hint", ""))}</small></div>'
            f"{badge_html}</div>"
        )
    caption = diagram.get("caption")
    cap_html = f'<div class="dep-caption">{_esc(caption)}</div>' if caption else ""
    return (
        f'<div class="dep-diagram">'
        f'<div class="dep-diagram-title">{_esc(diagram.get("title", "依赖关系"))}</div>'
        f'{"".join(rows_html)}{cap_html}</div>'
    )


def _render_data_table(props: dict[str, Any]) -> str:
    props = _normalize_data_table_props(props)
    columns = props.get("columns") or []
    rows = props.get("rows") or []
    col_styles = _normalize_col_map(props.get("column_styles"))
    col_tags = _normalize_col_map(props.get("column_tags"))
    diagram = props.get("diagram")

    if not columns and not rows:
        if diagram:
            return f'<div class="table-box">{_render_dep_diagram(diagram)}</div>'
        return '<div class="table-box"><div class="table-title"></div><table class="data-table"><thead><tr></tr></thead><tbody></tbody></table></div>'

    def cell_class(col_idx: int, *, header: bool = False) -> str:
        key = str(col_idx)
        style = col_styles.get(key, "")
        if header and style:
            return f' class="{_esc(style)}"'
        if not header and style:
            return f' class="{_esc(style)}"'
        return ""

    head_cells = []
    for i, col in enumerate(columns):
        tag = col_tags.get(str(i), "")
        tag_html = f'<span class="col-tag">{_esc(tag)}</span>' if tag else ""
        head_cells.append(f"<th{cell_class(i, header=True)}>{_esc(col)}{tag_html}</th>")

    body_rows = []
    for row in rows:
        cells = []
        for i, val in enumerate(row):
            cells.append(f"<td{cell_class(i)}>{_esc(val)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    diagram = props.get("diagram")
    badge = _normalize_badge(props.get("badge"))
    badge_html = ""
    if badge and badge.get("text"):
        badge_html = (
            f'<span class="badge {_esc(badge.get("style", "warn"))}">'
            f'{_esc(badge.get("text", ""))}</span>'
        )

    return (
        f'<div class="table-box">'
        f'<div class="table-title">{_esc(props.get("title", ""))}</div>'
        f'<table class="data-table"><thead><tr>{"".join(head_cells)}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table>'
        f"{_render_dep_diagram(diagram) if diagram else ''}"
        f"{badge_html}</div>"
    )


def _render_title_card(props: dict[str, Any]) -> str:
    return (
        f'<div class="title-card">'
        f'<h2>{_esc(props.get("heading", ""))}</h2>'
        f'<span class="tag">{_esc(props.get("tag", ""))}</span></div>'
    )


def _render_step_panel(props: dict[str, Any]) -> str:
    steps_html: list[str] = []
    for i, step in enumerate(props.get("steps") or [], start=1):
        if not isinstance(step, dict):
            continue
        body = f"<p>{_esc(step.get('body', ''))}</p>"
        chips = step.get("chips") or []
        if chips:
            chips_html = "".join(f'<span class="pk-chip">{_esc(c)}</span>' for c in chips)
            body += f'<div class="pk-group">{chips_html}</div>'
        compare = step.get("compare")
        if compare:
            good = compare.get("good") or {}
            bad = compare.get("bad") or {}
            body += (
                '<div class="compare-grid">'
                f'<div class="compare-card good"><strong>✓ {_esc(good.get("title", ""))}</strong>'
                f'{_esc(good.get("body", ""))}</div>'
                f'<div class="compare-card bad"><strong>✗ {_esc(bad.get("title", ""))}</strong>'
                f'{_esc(bad.get("body", ""))}</div></div>'
            )
        steps_html.append(
            f'<div class="nf2-step"><div class="step-num">{i}</div>'
            f'<div class="step-body"><h4>{_esc(step.get("title", ""))}</h4>{body}</div></div>'
        )
    return (
        f'<div class="nf2-panel">'
        f'<h3>{_esc(props.get("heading", ""))}</h3>'
        f'<p class="nf2-lead">{_esc(props.get("lead", ""))}</p>'
        f'<div class="nf2-steps">{"".join(steps_html)}</div></div>'
    )


def _render_split_tables(props: dict[str, Any]) -> str:
    mini_blocks: list[str] = []
    for table in props.get("tables") or []:
        if not isinstance(table, dict):
            continue
        cols = table.get("columns") or []
        rows = table.get("rows") or []
        head = "".join(f"<th>{_esc(c)}</th>" for c in cols)
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in row) + "</tr>" for row in rows
        )
        mini_blocks.append(
            f'<div class="mini-table"><h4>{_esc(table.get("title", ""))}</h4>'
            f'<table class="data-table"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>"
        )
    diagram = props.get("diagram")
    diag_html = _render_dep_diagram(diagram) if diagram else ""
    wrap = f'<div style="margin-top:18px;">{diag_html}</div>' if diag_html else ""
    return f'<div class="split-tables">{"".join(mini_blocks)}</div>{wrap}'


def _render_summary_list(props: dict[str, Any]) -> str:
    items = "".join(
        f"<li>{_esc(_normalize_summary_item(x))}</li>"
        for x in (props.get("items") or [])
        if _normalize_summary_item(x)
    )
    footer = props.get("footer")
    footer_html = f'<div class="summary-footer">{_esc(footer)}</div>' if footer else ""
    return f'<ul class="summary-list">{items}</ul>{footer_html}'


def _render_visual(visual: dict[str, Any]) -> str:
    vtype = visual.get("type", "")
    props = visual.get("props") or {}
    if vtype == "title_card":
        return _render_title_card(_normalize_title_card_props(props))
    if vtype == "data_table":
        return _render_data_table(props)
    if vtype == "step_panel":
        return _render_step_panel(_normalize_step_panel_props(props))
    if vtype == "split_tables":
        return _render_split_tables(_normalize_split_tables_props(props))
    if vtype == "summary_list":
        return _render_summary_list(props)
    if vtype == "dep_diagram":
        return _render_dep_diagram(props)
    return f'<div class="table-box"><p>{_esc(props.get("body", "（未支持的 visual 类型）"))}</p></div>'


def render_scene_section(scene: dict[str, Any], index: int, *, active: bool = False) -> str:
    visual = scene.get("visual") or {}
    vtype = visual.get("type", "")
    narration = _esc(str(scene.get("narration") or scene.get("subtitle") or "").strip())
    caption = f'<div class="narration-caption">{narration}</div>'
    active_cls = " active" if active else ""
    body = _render_visual(visual)

    if vtype == "title_card":
        return (
            f'<section class="scene{active_cls}" data-index="{index}">'
            f"{body}{caption}</section>"
        )
    return (
        f'<section class="scene{active_cls}" data-index="{index}">'
        f'<div class="scene-content">{body}</div>{caption}</section>'
    )


def _extract_block(source: str, start_pat: str, end_pat: str) -> str:
    m = re.search(start_pat, source, re.DOTALL)
    if not m:
        raise ValueError(f"template block not found: {start_pat}")
    start = m.end()
    end = re.search(end_pat, source[start:])
    if not end:
        raise ValueError(f"template block end not found: {end_pat}")
    return source[start : start + end.start()]


def render_explainer_html(storyboard: dict[str, Any], output_path: Path) -> Path:
    """
    Write index.html — HTML animation player + hooks for audio/scene-XX.mp3.
    Style/script copied from demo/2nf-animation.html (HTML + 本地 MP3 方法).
    """
    if not DEMO_HTML.is_file():
        raise FileNotFoundError(f"Demo template missing: {DEMO_HTML}")

    demo = DEMO_HTML.read_text(encoding="utf-8")
    css = _extract_block(demo, r"<style>", r"</style>")
    css = css + NARRATION_CAPTION_CSS
    js = _extract_block(demo, r"<script>\s*\n\s*const FALLBACK_DURATIONS", r"</script>")
    js = "const FALLBACK_DURATIONS" + js
    js = re.sub(r"\n\s*detectLocalAudio\(\);\s*\Z", "", js.rstrip()) + "\n"

    title = _esc(storyboard.get("title") or "讲解动画")
    scenes = storyboard.get("scenes") or []
    scenes_html = "\n          ".join(
        render_scene_section(scene, i, active=(i == 0)) for i, scene in enumerate(scenes)
    )

    setup_html = f"""
    <div class="setup-overlay" id="setupOverlay">
      <div class="setup-card">
        <h2>{title}</h2>
        <p>HTML 分镜动画 + 本地 MP3 配音（edge-tts 预生成）。点击全屏开始，播完一镜自动切下一镜。</p>
        <div class="setup-actions">
          <button id="startBtn" class="primary">全屏开始（本地配音）</button>
          <button id="skipVoiceBtn" class="ghost">无配音仅全屏</button>
        </div>
        <div class="status-pill" id="setupStatus">检测 audio/manifest.json …</div>
      </div>
    </div>"""

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
{css}
  </style>
</head>
<body>
  <div id="app">
{setup_html}
    <div class="presentation">
      <div class="top-bar">
        <h1>{title}</h1>
        <div class="top-bar-right">
          <span class="voice-badge" id="voiceBadge">本地配音</span>
          <button id="settingsBtn" class="ghost" type="button" hidden>设置</button>
          <button id="fsBtn">进入全屏</button>
        </div>
      </div>
      <div class="stage-wrap">
        <div class="stage" id="stage">
          {scenes_html}
        </div>
      </div>
      <div class="controls">
        <div class="controls-left">
          <button id="prevBtn">上一镜</button>
          <button id="playBtn" class="primary">暂停</button>
          <button id="nextBtn">下一镜</button>
        </div>
        <div class="dots" id="dots"></div>
        <div class="controls-right">
          <span class="scene-label" id="sceneLabel">场景 1 / {len(scenes)}</span>
        </div>
      </div>
    </div>
  </div>
  <script>
{js}
    (function () {{
      setSpeakingVisual = function (active) {{
        scenes.forEach((scene, i) => {{
          const on = active && i === current;
          scene.querySelectorAll(".narration-caption, .subtitle-bar").forEach((el) => {{
            el.classList.toggle("speaking", on);
          }});
        }});
      }};

      const origDetect = detectLocalAudio;
      detectLocalAudio = async function () {{
        let done = false;
        const detectPromise = origDetect().finally(() => {{ done = true; }});
        const timeout = new Promise((resolve) => setTimeout(resolve, 2500));
        await Promise.race([detectPromise, timeout]);
        if (!done) {{
          localAudioReady = false;
          setupStatus.className = "status-pill";
          setupStatus.textContent = "配音检测超时，可先无配音播放。";
        }}
      }};

      const params = new URLSearchParams(location.search);
      if (params.get("embed") === "1") {{
        window.addEventListener("load", () => {{
          setTimeout(async () => {{
            await detectLocalAudio();
            await startPresentation(localAudioReady);
          }}, 200);
        }});
      }} else {{
        detectLocalAudio();
      }}
    }})();
  </script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    return output_path

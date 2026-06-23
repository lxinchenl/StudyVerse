"""Compose and normalize Python scripts for code-lab execution."""

from __future__ import annotations

import ast
import re
from typing import Any

_SQLITE_INIT_MARKERS = (
    "import sqlite3",
    "sqlite3.connect",
    "CREATE TABLE",
    "executemany(",
    "conn.commit()",
    "conn.close()",
)


def compose_lab_script(*, setup: str = "", code: str) -> str:
    setup = setup.strip()
    code = code.strip()
    if setup and code:
        return f"{setup}\n\n{code}\n"
    return code or setup


def validate_lab_script(setup: str, code: str) -> str | None:
    script = compose_lab_script(setup=setup, code=code)
    if not script.strip():
        return "代码为空"
    try:
        ast.parse(script)
    except SyntaxError as exc:
        return f"语法错误（第 {exc.lineno} 行）: {exc.msg}"
    return None


def prepare_submitted_code(*, setup: str, code: str) -> str:
    """Normalize user-submitted code before sandbox execution."""
    setup = setup.strip()
    code = code.strip()
    if setup:
        return _normalize_user_code(code)
    return code


def normalize_challenge_codes(challenge: dict[str, Any]) -> dict[str, Any]:
    """Fix common LLM mistakes: nested __main__, duplicate sqlite init when setup exists."""
    setup = str(challenge.get("setup_code") or "").strip()
    if not setup:
        return challenge

    for key in ("starter_code", "solution_code"):
        raw = str(challenge.get(key) or "").strip()
        if raw:
            challenge[key] = _normalize_user_code(raw)
    return challenge


def _normalize_user_code(code: str) -> str:
    extracted = _extract_conn_function(code)
    if extracted:
        name, func = extracted
        # 只保留 def 块 + 一次入口调用，避免把用户已有的 query_xxx(conn) 再追加一遍
        return f"{func}\n\n{name}(conn)\n"

    cleaned = _strip_main_blocks(code)
    cleaned = _strip_sqlite_init(cleaned)
    return cleaned.strip() + "\n"


def _extract_conn_function(code: str) -> tuple[str, str] | None:
    match = re.search(r"^def\s+(\w+)\s*\(\s*conn\s*\)\s*:", code, re.MULTILINE)
    if not match:
        return None
    name = match.group(1)
    rest = code[match.start() :]
    rest = re.split(r"\n\s*if\s+__name__\s*==", rest, maxsplit=1)[0]
    func_part = _extract_def_block(rest)
    if not func_part.startswith("def "):
        return None
    return name, func_part


def _extract_def_block(code: str) -> str:
    """Return only the def block, excluding module-level calls after it."""
    lines = code.splitlines()
    if not lines:
        return ""
    block = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            block.append(line)
            continue
        if line.startswith((" ", "\t")) or line.strip().startswith("#"):
            block.append(line)
            continue
        break
    return "\n".join(block).rstrip()


def _strip_main_blocks(code: str) -> str:
    return re.split(r"\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:", code, maxsplit=1)[0].rstrip()


def _strip_sqlite_init(code: str) -> str:
    lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if any(marker in stripped for marker in _SQLITE_INIT_MARKERS):
            continue
        if stripped.startswith("test_data"):
            continue
        lines.append(line)
    return "\n".join(lines)

"""Minimal Python execution sandbox for code-lab grading (stdout comparison)."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from app.infrastructure.code_lab_script import compose_lab_script, validate_lab_script

DEFAULT_TIMEOUT_SEC = 8.0
MAX_CODE_CHARS = 12000
BLOCKED_PATTERNS = (
    r"\bsubprocess\b",
    r"\bos\.system\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bopen\s*\([^)]*['\"]w",
    r"\bshutil\.rmtree\b",
    r"\bsocket\b",
    r"\brequests\b",
    r"\bhttpx\b",
)


def _validate_code(code: str) -> str | None:
    if len(code) > MAX_CODE_CHARS:
        return f"代码超过 {MAX_CODE_CHARS} 字符限制"
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return f"代码包含不允许的操作：{pattern}"
    return None


def normalize_stdout(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def run_python(*, setup: str = "", code: str, timeout: float = DEFAULT_TIMEOUT_SEC) -> dict[str, str | int]:
    """Run setup + user code in isolated subprocess; return stdout/stderr/exit_code."""
    err = _validate_code(f"{setup}\n{code}")
    if err:
        return {"ok": False, "stdout": "", "stderr": err, "exit_code": -1, "error": err}

    syntax_err = validate_lab_script(setup, code)
    if syntax_err:
        return {"ok": False, "stdout": "", "stderr": syntax_err, "exit_code": -1, "error": syntax_err}

    script = compose_lab_script(setup=setup, code=code)
    with tempfile.TemporaryDirectory(prefix="edu_code_lab_") as tmp:
        script_path = Path(tmp) / "main.py"
        script_path.write_text(script, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            return {
                "ok": proc.returncode == 0,
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or "",
                "exit_code": int(proc.returncode),
                "error": "",
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"运行超时（>{timeout}s）",
            }
        except Exception as exc:
            return {
                "ok": False,
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "error": str(exc),
            }


def compare_stdout(user_stdout: str, reference_stdout: str) -> bool:
    return normalize_stdout(user_stdout) == normalize_stdout(reference_stdout)

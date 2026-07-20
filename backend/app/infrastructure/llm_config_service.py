import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "doubao-seed-2-1-turbo-260628"

DOUBAO_MODEL_IDS = frozenset(
    {
        "doubao-seed-2-1-pro-260628",
        "doubao-seed-2-1-turbo-260628",
        "doubao-seed-evolving",
    }
)
DEEPSEEK_MODEL_IDS = frozenset(
    {
        "deepseek-v4-pro-260425",
        "deepseek-v4-flash-260425",
        "deepseek-chat",
        "deepseek-reasoner",
    }
)


def model_family(model: str, provider: str | None = None) -> str:
    mid = str(model or "").strip()
    if str(provider or "").strip() == "mock" or mid == "mock":
        return "mock"
    if mid in DEEPSEEK_MODEL_IDS or mid.startswith("deepseek"):
        return "deepseek"
    return "doubao"


class LLMConfigService:
    """Per-user LLM settings: Doubao / DeepSeek API keys + selected model."""

    def __init__(self, users_dir: Path):
        self.users_dir = users_dir
        self.users_dir.mkdir(parents=True, exist_ok=True)

    def _config_path(self, user_id: str) -> Path:
        return self.users_dir / user_id / "llm.json"

    def get_config(self, user_id: str) -> dict[str, Any]:
        path = self._config_path(user_id)
        if path.exists():
            return self._normalize(json.loads(path.read_text(encoding="utf-8")))
        return self._normalize(self._defaults())

    def save_config(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        current = self.get_config(user_id)
        merged = {**current}
        for key, value in data.items():
            if value is None:
                continue
            if key in {"doubao_api_key", "deepseek_api_key"} and not str(value).strip():
                continue
            merged[key] = value
        normalized = self._normalize(merged)

        # Reject selecting a family without its key (except mock).
        family = model_family(normalized["model"], normalized["provider"])
        unlocked = self._unlocked_families(normalized)
        if family not in unlocked:
            # If user only updated keys and previous model became invalid, fall back.
            if "model" in data or "provider" in data:
                raise ValueError(
                    "该模型尚未解锁：请先在设置页填写对应厂商的 API Key"
                    if family != "mock"
                    else "无法使用该模型"
                )
            if "doubao" in unlocked:
                normalized["provider"] = "openai_compatible"
                normalized["model"] = DEFAULT_MODEL
            elif "deepseek" in unlocked:
                normalized["provider"] = "openai_compatible"
                normalized["model"] = "deepseek-v4-flash-260425"
            else:
                normalized["provider"] = "mock"
                normalized["model"] = "mock"

        self._write_file(user_id, normalized)
        return normalized

    def public_view(self, user_id: str) -> dict[str, Any]:
        cfg = self.get_config(user_id)
        doubao_key = cfg.get("doubao_api_key", "")
        deepseek_key = cfg.get("deepseek_api_key", "")
        unlocked = sorted(self._unlocked_families(cfg))
        return {
            "provider": cfg["provider"],
            "model": cfg["model"],
            "base_url": self._base_url_for(cfg),
            "doubao_api_key_set": bool(doubao_key),
            "doubao_api_key_hint": self._mask_key(doubao_key),
            "deepseek_api_key_set": bool(deepseek_key),
            "deepseek_api_key_hint": self._mask_key(deepseek_key),
            "unlocked_families": unlocked,
            "ready": bool(unlocked),
            # Backward-compatible fields for older clients
            "api_key_set": bool(doubao_key or deepseek_key),
            "api_key_hint": self._mask_key(doubao_key or deepseek_key),
        }

    def resolve_runtime(self, user_id: str) -> dict[str, Any]:
        """Resolve provider kwargs for the user's currently selected model."""
        cfg = self.get_config(user_id)
        family = model_family(cfg["model"], cfg["provider"])
        if family == "mock":
            return {"provider": "mock", "model": "mock", "api_key": "", "base_url": "", "use_responses_api": False}

        if family == "deepseek":
            key = cfg.get("deepseek_api_key", "")
            if not key:
                return {"provider": "mock", "model": "mock", "api_key": "", "base_url": "", "use_responses_api": False}
            return {
                "provider": "openai_compatible",
                "model": cfg["model"],
                "api_key": key,
                "base_url": DEEPSEEK_BASE_URL,
                "use_responses_api": False,
            }

        key = cfg.get("doubao_api_key", "")
        if not key:
            return {"provider": "mock", "model": "mock", "api_key": "", "base_url": "", "use_responses_api": False}
        return {
            "provider": "openai_compatible",
            "model": cfg["model"],
            "api_key": key,
            "base_url": DOUBAO_BASE_URL,
            # Doubao Seed 2.1 / evolving go through Responses API endpoint.
            "use_responses_api": True,
        }

    def _write_file(self, user_id: str, normalized: dict[str, Any]) -> None:
        path = self._config_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": normalized["provider"],
            "model": normalized["model"],
        }
        if normalized.get("doubao_api_key"):
            payload["doubao_api_key"] = normalized["doubao_api_key"]
        if normalized.get("deepseek_api_key"):
            payload["deepseek_api_key"] = normalized["deepseek_api_key"]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _defaults(self) -> dict[str, Any]:
        # Optional env seed for first-time convenience (still stored per-user on save).
        doubao = os.getenv("ARK_API_KEY", "").strip() or os.getenv("DOUBAO_API_KEY", "").strip()
        deepseek = os.getenv("DEEPSEEK_API_KEY", "").strip()
        provider = "openai_compatible" if doubao or deepseek else "mock"
        model = DEFAULT_MODEL if doubao else ("deepseek-v4-flash-260425" if deepseek else "mock")
        return {
            "provider": provider,
            "model": model,
            "doubao_api_key": doubao,
            "deepseek_api_key": deepseek,
        }

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        cfg = deepcopy(data)
        # Migrate legacy single api_key → doubao_api_key
        legacy_key = str(cfg.pop("api_key", "") or "").strip()
        cfg["doubao_api_key"] = str(cfg.get("doubao_api_key") or legacy_key or "").strip()
        cfg["deepseek_api_key"] = str(cfg.get("deepseek_api_key") or "").strip()
        cfg["model"] = str(cfg.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        cfg["provider"] = str(cfg.get("provider") or "mock").strip() or "mock"
        if cfg["model"] == "mock":
            cfg["provider"] = "mock"
        elif cfg["provider"] == "mock" and cfg["model"] != "mock":
            cfg["provider"] = "openai_compatible"
        # Drop obsolete fields
        cfg.pop("base_url", None)
        return cfg

    def _unlocked_families(self, cfg: dict[str, Any]) -> set[str]:
        unlocked = {"mock"}
        if cfg.get("doubao_api_key"):
            unlocked.add("doubao")
        if cfg.get("deepseek_api_key"):
            unlocked.add("deepseek")
        return unlocked

    def _base_url_for(self, cfg: dict[str, Any]) -> str:
        family = model_family(cfg["model"], cfg["provider"])
        if family == "deepseek":
            return DEEPSEEK_BASE_URL
        if family == "doubao":
            return DOUBAO_BASE_URL
        return ""

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{'*' * (len(key) - 4)}{key[-4:]}"

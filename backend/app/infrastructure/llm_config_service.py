import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-2-0-lite-260428"


class LLMConfigService:
    """Persist LLM settings (base URL, model, API key) for web configuration."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            return self._normalize(json.loads(self.config_path.read_text(encoding="utf-8")))
        data = self._normalize(self._defaults_from_env())
        if data.get("api_key"):
            self._write_file(data)
        return data

    def save_config(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.config_path.exists():
            current = self._normalize(json.loads(self.config_path.read_text(encoding="utf-8")))
        else:
            current = self._normalize(self._defaults_from_env())
        merged = {**current, **{k: v for k, v in data.items() if v is not None}}
        if "api_key" in data and not str(data.get("api_key", "")).strip():
            merged["api_key"] = current.get("api_key", "")
        normalized = self._normalize(merged)
        self._write_file(normalized)
        return normalized

    def _write_file(self, normalized: dict[str, Any]) -> None:
        payload = {
            "provider": normalized["provider"],
            "base_url": normalized["base_url"],
            "model": normalized["model"],
        }
        if normalized.get("api_key"):
            payload["api_key"] = normalized["api_key"]
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def public_view(self) -> dict[str, Any]:
        cfg = self.get_config()
        key = cfg.get("api_key", "")
        return {
            "provider": cfg["provider"],
            "base_url": cfg["base_url"],
            "model": cfg["model"],
            "api_key_set": bool(key),
            "api_key_hint": self._mask_key(key),
            "ready": cfg["provider"] == "mock" or bool(key),
        }

    def _defaults_from_env(self) -> dict[str, Any]:
        api_key = os.getenv("ARK_API_KEY", "").strip()
        provider = os.getenv("EDU_AGENT_LLM_PROVIDER", "openai_compatible" if api_key else "mock")
        return {
            "provider": provider,
            "base_url": os.getenv("EDU_AGENT_LLM_BASE_URL", DEFAULT_BASE_URL),
            "model": os.getenv("EDU_AGENT_LLM_MODEL", DEFAULT_MODEL),
            "api_key": api_key,
        }

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        cfg = deepcopy(data)
        cfg["provider"] = cfg.get("provider") or "mock"
        cfg["base_url"] = (cfg.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        cfg["model"] = cfg.get("model") or DEFAULT_MODEL
        cfg["api_key"] = str(cfg.get("api_key") or "").strip()
        return cfg

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{'*' * (len(key) - 4)}{key[-4:]}"

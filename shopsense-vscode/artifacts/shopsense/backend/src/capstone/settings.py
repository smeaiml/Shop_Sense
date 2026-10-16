"""Project-root-aware configuration for the ShopSense demo."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data" / "shopsense"
RUNTIME_DIR = Path(os.environ.get("SHOP_SENSE_RUNTIME_DIR", PROJECT_ROOT / "runtime"))
DATABASE_PATH = Path(os.environ.get("SHOP_SENSE_DB_PATH", RUNTIME_DIR / "shopsense.sqlite3"))
POLICY_DIR = DATA_DIR / "corpus" / "markdown"


@lru_cache(maxsize=8)
def load_config(name: str) -> dict[str, Any]:
    """Load a known YAML configuration file; fail explicitly on malformed config."""
    if name not in {"app", "retrieval", "guardrails", "evaluation"}:
        raise ValueError("Unknown ShopSense configuration.")
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Required configuration not found: {path}")
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return content


def llm_settings() -> dict[str, Any]:
    app = load_config("app")
    configured = app.get("llm", {})
    if not isinstance(configured, dict):
        configured = {}
    provider = os.getenv("LLM_PROVIDER", str(configured.get("provider", "openai"))).strip().lower()
    model = os.getenv("LLM_MODEL", str(configured.get("model", "gpt-5-mini"))).strip()
    enabled = os.getenv("LLM_ENABLED", str(configured.get("enabled", True))).strip().lower()
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    return {
        "provider": provider,
        "model": model,
        "enabled": enabled not in {"0", "false", "no", "off"},
        "base_url": base_url,
        "api_key": os.getenv("OPENAI_API_KEY"),
        "timeout_seconds": float(configured.get("timeout_seconds", 12)),
        "max_retries": int(configured.get("max_retries", 2)),
    }

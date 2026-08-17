from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def product_config(path: str = "config/product.yaml") -> dict[str, Any]:
    return _load_yaml(path)


@lru_cache(maxsize=1)
def source_priority_config(path: str = "config/source_priority.yaml") -> dict[str, int]:
    payload = _load_yaml(path)
    priorities = payload.get("source_priority", {})
    return {
        str(key): int(value)
        for key, value in priorities.items()
        if isinstance(value, int)
    }


def _load_yaml(path: str) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}

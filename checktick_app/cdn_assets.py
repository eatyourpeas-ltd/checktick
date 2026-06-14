import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_MANIFEST_PATH = Path(__file__).resolve().with_name("cdn_assets.json")


@lru_cache(maxsize=4)
def _load_assets_for_mtime(mtime_ns: int) -> dict[str, Any]:
    del mtime_ns
    with _MANIFEST_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assets: dict[str, Any] = {}
    for item in data.get("assets", []):
        key = item.get("key")
        if not key:
            continue
        assets[key] = item

    return assets


def get_cdn_assets() -> dict[str, Any]:
    if not _MANIFEST_PATH.exists():
        return {}

    return _load_assets_for_mtime(_MANIFEST_PATH.stat().st_mtime_ns)

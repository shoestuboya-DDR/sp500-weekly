"""data.json の組み立てと書き出し。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from parse import PricePoint
from weekly import WeekPoint


def build_payload(
    config: dict, weeks: list[WeekPoint], prices: list[PricePoint], generated_at: datetime
) -> dict:
    return {
        "fund": {"name": config["fund_name"], "isin": config["isin"]},
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "source_latest_date": prices[-1][0].isoformat(),
        "source_row_count": len(prices),
        "alert_threshold_pct": config["alert_threshold_pct"],
        "display_weeks": config["display_weeks"],
        "stale_days": config["stale_days"],
        "weeks": [w.to_dict() for w in weeks],
    }


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict) -> None:
    """一時ファイルに書いてから置き換える（途中で落ちても壊れたファイルを残さない）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)

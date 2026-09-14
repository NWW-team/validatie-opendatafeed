"""Een opgehaalde feed bewaren en terugladen.

Handig om twee dingen: een peilmoment vastleggen als bewijs, en de regels
opnieuw draaien zonder de feed nog eens te belasten.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .models import CountryRecord, FeedSnapshot


def save_snapshot(snapshot: FeedSnapshot, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(snapshot)
    data["fetched_at"] = snapshot.fetched_at.astimezone(UTC).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> FeedSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = [CountryRecord(**record) for record in data.get("records", [])]
    return FeedSnapshot(
        fetched_at=datetime.fromisoformat(data["fetched_at"]),
        base_url=data.get("base_url", ""),
        countries=data.get("countries", []),
        traveladvice_index=data.get("traveladvice_index", []),
        representation_index=data.get("representation_index", []),
        emergency_info=data.get("emergency_info", []),
        records=records,
        fetch_errors=data.get("fetch_errors", {}),
    )

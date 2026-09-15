"""Een opgehaalde feed bewaren en terugladen.

Handig om twee dingen: een peilmoment vastleggen als bewijs, en de regels
opnieuw draaien zonder de feed nog eens te belasten.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import CountryRecord, FeedSnapshot


def save_snapshot(snapshot: FeedSnapshot, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(snapshot)
    data["fetched_at"] = snapshot.fetched_at.astimezone(UTC).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> FeedSnapshot:
    """Lees een bewaarde feed terug tot dezelfde snapshot.

    De velden worden uit het dataclass afgeleid en niet één voor één
    opgesomd. Een opsomming raakt namelijk stil achter: ``rate_limited``
    ontbrak er eerder in, waardoor een peiling die was afgeknepen bij
    herdraaien niet meer meldde dat hij onvolledig was — precies het
    onderscheid waar regel F10 voor bestaat.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    velden: dict[str, Any] = {
        veld.name: data[veld.name] for veld in fields(FeedSnapshot) if veld.name in data
    }
    velden["fetched_at"] = datetime.fromisoformat(data["fetched_at"])
    velden["records"] = [CountryRecord(**record) for record in data.get("records", [])]
    return FeedSnapshot(**velden)

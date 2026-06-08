from __future__ import annotations

from collections import Counter
from typing import Iterable

from app.models.schemas import SongEntry


def collect_tag_distribution(songs: Iterable[SongEntry]) -> dict[str, dict[str, int]]:
    buckets: dict[str, Counter[str]] = {}
    for song in songs:
        for tag in song.tags:
            bucket = buckets.setdefault(tag.key, Counter())
            bucket[tag.value] += 1
    return {k: dict(v) for k, v in buckets.items()}


def suggest_training_tags(weak_dimensions: list[str]) -> list[str]:
    mapping = {
        "breakthrough": ["style:tech", "stamina:high"],
        "stability": ["style:balance", "reading:low"],
        "accuracy": ["style:flow", "reading:mid"],
        "coverage": ["style:swing", "style:jack", "style:tech"],
        "b50_coverage": ["style:swing", "style:jack", "style:tech"],
        "full_coverage": ["style:balance", "reading:mid", "stamina:mid"],
        "growth": ["stamina:mid", "reading:mid"],
        "resilience": ["style:balance", "stamina:high"],
        "rating_w": ["style:balance", "reading:mid"],
        "level_adapt": ["style:balance", "stamina:mid"],
        "accuracy_dx": ["style:flow", "reading:high"],
        "stamina_base": ["stamina:high", "style:tech"],
        "technique_gap": ["style:jack", "style:tech", "reading:high"],
        "mindset": ["style:balance", "reading:low"],
    }
    out: list[str] = []
    for key in weak_dimensions:
        out.extend(mapping.get(key, []))
    return list(dict.fromkeys(out))

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

import numpy as np

from app.kb.repository import SongRepository
from app.models.schemas import DimensionScore, RadarOutput


@dataclass
class FeatureContext:
    rating: float
    achievements: list[float]
    ds_values: list[float]
    song_titles: list[str]


class SixDimEngine:
    def __init__(self, song_repo: SongRepository) -> None:
        self.song_repo = song_repo

    def _extract(self, payload: dict[str, Any]) -> FeatureContext:
        charts = payload.get("charts", {})
        sd = charts.get("sd", []) or []
        dx = charts.get("dx", []) or []
        all_scores = sd + dx
        achievements = [float(item.get("achievements", 0.0)) for item in all_scores]
        ds_values = [float(item.get("ds", 0.0)) for item in all_scores]
        titles = [str(item.get("title", "")) for item in all_scores if item.get("title")]
        rating = float(payload.get("rating", 0.0) or 0.0)
        return FeatureContext(rating=rating, achievements=achievements, ds_values=ds_values, song_titles=titles)

    @staticmethod
    def _scale(value: float, low: float, high: float) -> float:
        if high <= low:
            return 50.0
        raw = (value - low) / (high - low) * 100.0
        return float(np.clip(raw, 0.0, 100.0))

    def score(self, player_id: str, payload: dict[str, Any]) -> RadarOutput:
        ctx = self._extract(payload)
        achievements = ctx.achievements or [0.0]
        ds_values = ctx.ds_values or [0.0]

        breakthrough = self._scale(mean(ds_values), 11.5, 15.0)
        stability = self._scale(100 - float(np.std(achievements)) * 2.2, 40, 100)
        accuracy = self._scale(mean(achievements), 92.0, 101.0)

        kb_titles = {song.title for song in self.song_repo.list_all()}
        coverage_ratio = len(set(ctx.song_titles) & kb_titles) / max(len(kb_titles), 1)
        coverage = self._scale(coverage_ratio, 0.05, 0.80)

        top_10 = sorted(achievements, reverse=True)[:10]
        growth = self._scale(mean(top_10) - mean(achievements), -2.0, 4.0)

        dims_tmp = [breakthrough, stability, accuracy, coverage, growth]
        resilience = self._scale(min(dims_tmp) - (mean(dims_tmp) - 12.0), -40, 40)

        dimensions = [
            DimensionScore(key="breakthrough", name="定数突破力", score=round(breakthrough, 2), reason="来自B50平均定数与高定数承压能力"),
            DimensionScore(key="stability", name="稳定率", score=round(stability, 2), reason="来自达成率离散度和低分尾部抑制"),
            DimensionScore(key="accuracy", name="准度", score=round(accuracy, 2), reason="来自B50总体达成率质量"),
            DimensionScore(key="coverage", name="覆盖面", score=round(coverage, 2), reason="来自不同标签曲目覆盖比例"),
            DimensionScore(key="growth", name="成长性", score=round(growth, 2), reason="来自头部成绩与整体差值反映上升潜力"),
            DimensionScore(key="resilience", name="短板韧性", score=round(resilience, 2), reason="来自短板与均值差距控制能力"),
        ]

        sorted_dims = sorted(dimensions, key=lambda d: d.score)
        shortfalls = [d.key for d in sorted_dims[:2]]
        strengths = [d.key for d in sorted(dimensions, key=lambda d: d.score, reverse=True)[:2]]
        return RadarOutput(
            player_id=player_id,
            dimensions=dimensions,
            shortfalls=shortfalls,
            strengths=strengths,
            evaluation_model="legacy",
            w_tier=None,
            stage=None,
        )

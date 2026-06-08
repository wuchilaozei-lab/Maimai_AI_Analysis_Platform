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
    chart_types: list[str]


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
        chart_types = [str(item.get("type", "")).lower() for item in all_scores if item.get("type")]
        rating = float(payload.get("rating", 0.0) or 0.0)
        return FeatureContext(
            rating=rating,
            achievements=achievements,
            ds_values=ds_values,
            song_titles=titles,
            chart_types=chart_types,
        )

    @staticmethod
    def _scale(value: float, low: float, high: float) -> float:
        if high <= low:
            return 50.0
        raw = (value - low) / (high - low) * 100.0
        return float(np.clip(raw, 0.0, 100.0))

    @staticmethod
    def _chart_key(item: dict[str, Any]) -> tuple[str, str, str]:
        title = str(item.get("title", "")).strip().lower()
        level = str(item.get("level_label") or item.get("level") or "").strip().lower()
        chart_type = str(item.get("type", "")).strip().lower()
        return title, level, chart_type

    def _b50_coverage(self, ctx: FeatureContext, ds_values: list[float]) -> float:
        unique_title_ratio = len(set(ctx.song_titles)) / max(len(ctx.song_titles), 1)
        ds_buckets = {
            int(ds * 10) // 5
            for ds in ds_values
            if ds > 0
        }
        ds_bucket_ratio = min(len(ds_buckets) / 8, 1.0)
        type_ratio = min(len(set(ctx.chart_types)) / 2, 1.0) if ctx.chart_types else 0.5
        return float(np.clip((unique_title_ratio * 0.45 + ds_bucket_ratio * 0.4 + type_ratio * 0.15) * 100, 0, 100))

    def _full_coverage(self, records_payload: dict[str, Any] | None, ds_values: list[float], b50_coverage: float) -> tuple[float, list[str], dict[str, float]]:
        if not records_payload:
            return (
                b50_coverage,
                ["未启用全量成绩，暂以B50覆盖作为代理"],
                {"records_available": 0.0},
            )

        records = records_payload.get("records", []) or []
        if not records:
            return 0.0, ["全量成绩为空"], {"records_available": 1.0, "records_count": 0.0}

        avg_ds = mean(ds_values) if ds_values else 0.0
        low = max(1.0, avg_ds - 1.0)
        high = min(15.0, avg_ds + 0.6)
        target_records = [
            item
            for item in records
            if low <= float(item.get("ds", 0.0) or 0.0) <= high
        ]
        played_keys = {self._chart_key(item) for item in target_records}
        repo_targets = [
            song
            for song in self.song_repo.filter_by_ds(min_ds=low, max_ds=high)
            if any(name in song.difficulty.lower() for name in ["expert", "master", "re:master"])
        ]
        repo_count = max(len(repo_targets), 1)
        chart_ratio = len(played_keys) / repo_count
        ds_buckets = {
            int(float(item.get("ds", 0.0) or 0.0) * 10) // 5
            for item in target_records
            if float(item.get("ds", 0.0) or 0.0) > 0
        }
        bucket_ratio = min(len(ds_buckets) / 8, 1.0)
        volume_score = self._scale(len(target_records), 25, 180)
        score = (
            self._scale(chart_ratio, 0.03, 0.35) * 0.45
            + bucket_ratio * 100 * 0.30
            + volume_score * 0.25
        )
        return (
            float(np.clip(score, 0, 100)),
            [f"全量记录={len(records)}", f"目标区间={low:.1f}-{high:.1f}", f"目标区间记录={len(target_records)}"],
            {
                "records_available": 1.0,
                "records_count": float(len(records)),
                "target_records": float(len(target_records)),
                "target_repo_charts": float(repo_count),
                "chart_ratio": round(chart_ratio, 4),
            },
        )

    def score(self, player_id: str, payload: dict[str, Any], records_payload: dict[str, Any] | None = None) -> RadarOutput:
        ctx = self._extract(payload)
        achievements = ctx.achievements or [0.0]
        ds_values = ctx.ds_values or [0.0]

        paired = list(zip(ds_values, achievements, strict=False))
        sorted_by_ds = sorted(paired, key=lambda item: item[0], reverse=True)
        high_ds_mean = mean([item[0] for item in sorted_by_ds[:10]]) if sorted_by_ds else 0.0
        max_ds = max(ds_values) if ds_values else 0.0
        breakthrough = (
            self._scale(high_ds_mean, 12.5, 15.0) * 0.7
            + self._scale(max_ds, 13.0, 15.0) * 0.3
        )

        bottom_10 = sorted(achievements)[:10]
        std_ach = float(np.std(achievements))
        stability = (
            self._scale(mean(bottom_10), 94.0, 100.5) * 0.65
            + self._scale(3.2 - std_ach, 0.0, 3.2) * 0.35
        )
        accuracy = self._scale(mean(achievements), 96.0, 100.8)

        b50_coverage = self._b50_coverage(ctx, ds_values)
        full_coverage, full_coverage_evidence, full_coverage_indicators = self._full_coverage(
            records_payload=records_payload,
            ds_values=ds_values,
            b50_coverage=b50_coverage,
        )

        charts = payload.get("charts", {})
        b35_ach = [float(item.get("achievements", 0.0)) for item in (charts.get("sd", []) or [])]
        b15_ach = [float(item.get("achievements", 0.0)) for item in (charts.get("dx", []) or [])]
        b35_ds = [float(item.get("ds", 0.0)) for item in (charts.get("sd", []) or [])]
        b15_ds = [float(item.get("ds", 0.0)) for item in (charts.get("dx", []) or [])]
        if b35_ach and b15_ach:
            new_chart_quality = mean(b15_ach) - mean(b35_ach)
            new_chart_ds = mean(b15_ds or [0.0]) - mean(b35_ds or [0.0])
            growth = (
                self._scale(new_chart_quality, -3.0, 1.5) * 0.6
                + self._scale(new_chart_ds, -0.8, 0.5) * 0.4
            )
        else:
            top_10 = sorted(achievements, reverse=True)[:10]
            growth = self._scale(mean(top_10) - mean(achievements), -0.5, 3.0)

        dims_tmp = [breakthrough, stability, accuracy, b50_coverage, full_coverage, growth]
        resilience = (
            self._scale(mean(bottom_10), 93.0, 100.0) * 0.55
            + self._scale(min(dims_tmp), 35.0, 85.0) * 0.45
        )

        dimensions = [
            DimensionScore(key="breakthrough", name="定数突破力", score=round(breakthrough, 2), reason="来自B50平均定数与高定数承压能力"),
            DimensionScore(key="stability", name="稳定率", score=round(stability, 2), reason="来自达成率离散度和低分尾部抑制"),
            DimensionScore(key="accuracy", name="准度", score=round(accuracy, 2), reason="来自B50总体达成率质量"),
            DimensionScore(
                key="b50_coverage",
                name="B50覆盖面",
                score=round(b50_coverage, 2),
                reason="来自B50内曲目去重、定数跨度和SD/DX类型分布",
            ),
            DimensionScore(
                key="full_coverage",
                name="全量覆盖面",
                score=round(full_coverage, 2),
                reason="来自全量成绩在当前训练区间的曲目覆盖",
                evidence=full_coverage_evidence,
                indicators=full_coverage_indicators,
            ),
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

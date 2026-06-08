from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean
from typing import Any

import numpy as np

from app.models.schemas import DimensionScore, RadarOutput, SkillGap, TrainingStrategy


@dataclass
class S4Profile:
    rating: float
    achievements: list[float]
    ds_values: list[float]
    dx_scores: list[float]
    rates: list[str]
    fcs: list[str]
    titles: list[str]
    level_labels: list[str]


class S4Evaluator:
    def _extract(self, payload: dict[str, Any]) -> S4Profile:
        charts = payload.get("charts", {})
        all_scores = (charts.get("sd", []) or []) + (charts.get("dx", []) or [])
        return S4Profile(
            rating=float(payload.get("rating", 0.0) or 0.0),
            achievements=[float(i.get("achievements", 0.0)) for i in all_scores],
            ds_values=[float(i.get("ds", 0.0)) for i in all_scores],
            dx_scores=[float(i.get("dxScore", 0.0) or 0.0) for i in all_scores],
            rates=[str(i.get("rate", "")).lower() for i in all_scores],
            fcs=[str(i.get("fc", "")).lower() for i in all_scores],
            titles=[str(i.get("title", "")) for i in all_scores if i.get("title")],
            level_labels=[str(i.get("level_label", "")).lower() for i in all_scores if i.get("level_label")],
        )

    @staticmethod
    def _scale(value: float, low: float, high: float) -> float:
        if high <= low:
            return 50.0
        raw = (value - low) / (high - low) * 100.0
        return float(np.clip(raw, 0.0, 100.0))

    @staticmethod
    def _w_tier(rating: float) -> str:
        if rating >= 16000:
            return "万六"
        if rating >= 15000:
            return "W6"
        if rating >= 14500:
            return "W5"
        if rating >= 13000:
            return "W4"
        if rating >= 11500:
            return "W3"
        return "W1-W2"

    @staticmethod
    def _stage_by_tier(tier: str) -> str:
        mapping = {
            "万六": "分水岭精修期",
            "W6": "分水岭突破期",
            "W5": "基础补齐期",
            "W4": "中级积累期",
            "W3": "紫谱适应期",
            "W1-W2": "基础建立期",
        }
        return mapping.get(tier, "基础建立期")

    @staticmethod
    def _percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
        return ordered[idx]

    @staticmethod
    def _range(low: float, high: float, ceiling: float) -> list[float]:
        low = round(max(1.0, low), 1)
        high = round(min(15.0, high, ceiling), 1)
        return [low, max(low, high)]

    def evaluate(self, player_id: str, payload: dict[str, Any]) -> tuple[RadarOutput, list[SkillGap], TrainingStrategy, dict[str, Any], dict[str, Any]]:
        profile = self._extract(payload)
        achievements = profile.achievements or [0.0]
        ds_values = profile.ds_values or [0.0]
        rates = profile.rates
        fcs = profile.fcs

        w_tier = self._w_tier(profile.rating)
        stage = self._stage_by_tier(w_tier)

        rating_dim = self._scale(profile.rating, 10000, 16500)
        # 等级适应力按玩家当前B50均值浮动，避免低/中段玩家被固定14区间误判。
        avg_ds = mean(ds_values)
        target_low = max(10.0, avg_ds - 0.2)
        target_high = min(15.0, avg_ds + 0.5)
        in_target_ratio = sum(1 for ds in ds_values if target_low <= ds <= target_high) / max(len(ds_values), 1)
        push_ratio = sum(1 for ds in ds_values if avg_ds + 0.2 <= ds <= avg_ds + 0.8) / max(len(ds_values), 1)
        level_adapt_dim = self._scale(in_target_ratio * 70 + push_ratio * 30, 18, 70)
        # 准度：达成率与高评级占比
        high_rate_ratio = sum(1 for r in rates if r in {"sss", "sssp", "ssp"}) / max(len(rates), 1)
        accuracy_dim = self._scale(mean(achievements) * 0.7 + high_rate_ratio * 100 * 0.3, 92, 101)
        # 底力体力：中高定数承压 + FC稳定
        high_ds_ratio = sum(1 for ds in ds_values if ds >= 13.7) / max(len(ds_values), 1)
        fc_ratio = sum(1 for fc in fcs if fc in {"fc", "fcp", "ap", "app"}) / max(len(fcs), 1)
        stamina_dim = self._scale((high_ds_ratio * 100) * 0.6 + (fc_ratio * 100) * 0.4, 20, 90)
        # 技巧短板：用分布跨度 + 方差作为代理
        ds_span = max(ds_values) - min(ds_values) if ds_values else 0
        std_ach = float(np.std(achievements))
        technique_dim = self._scale(100 - std_ach * 2.4 + ds_span * 4, 35, 110)
        # 心态玄学：用波动控制 + 头部稳定作软指标
        top10 = sorted(achievements, reverse=True)[:10] or [0.0]
        mindset_dim = self._scale(mean(top10) - std_ach, 84, 101)

        dims = [
            DimensionScore(
                key="rating_w",
                name="Rating/W值",
                score=round(rating_dim, 2),
                reason="按W值分层评估当前阶段",
                weight=0.22,
                level="优势" if rating_dim >= 70 else "待提升",
                evidence=[f"rating={profile.rating}", f"w_tier={w_tier}"],
                indicators={"rating": round(profile.rating, 2)},
            ),
            DimensionScore(
                key="level_adapt",
                name="谱面等级适应力",
                score=round(level_adapt_dim, 2),
                reason="关注当前水平附近的训练区覆盖",
                weight=0.18,
                level="优势" if level_adapt_dim >= 65 else "待提升",
                evidence=[f"目标区间={target_low:.1f}-{target_high:.1f}", f"目标区间占比={in_target_ratio:.2f}"],
                indicators={
                    "target_low": round(target_low, 3),
                    "target_high": round(target_high, 3),
                    "in_target_ratio": round(in_target_ratio, 4),
                    "push_ratio": round(push_ratio, 4),
                },
            ),
            DimensionScore(
                key="accuracy_dx",
                name="准度/DX分",
                score=round(accuracy_dim, 2),
                reason="达成率质量与高评级占比综合",
                weight=0.2,
                level="优势" if accuracy_dim >= 70 else "待提升",
                evidence=[f"mean_ach={mean(achievements):.2f}", f"high_rate_ratio={high_rate_ratio:.2f}"],
                indicators={"mean_ach": round(mean(achievements), 3), "high_rate_ratio": round(high_rate_ratio, 4)},
            ),
            DimensionScore(
                key="stamina_base",
                name="底力与体力",
                score=round(stamina_dim, 2),
                reason="高定数承压与FC稳定共同决定",
                weight=0.16,
                level="优势" if stamina_dim >= 65 else "待提升",
                evidence=[f"high_ds_ratio={high_ds_ratio:.2f}", f"fc_ratio={fc_ratio:.2f}"],
                indicators={"high_ds_ratio": round(high_ds_ratio, 4), "fc_ratio": round(fc_ratio, 4)},
            ),
            DimensionScore(
                key="technique_gap",
                name="技巧短板",
                score=round(technique_dim, 2),
                reason="按分布跨度与波动识别技巧短板",
                weight=0.14,
                level="优势" if technique_dim >= 65 else "待提升",
                evidence=[f"ds_span={ds_span:.2f}", f"ach_std={std_ach:.2f}"],
                indicators={"ds_span": round(ds_span, 3), "ach_std": round(std_ach, 3)},
            ),
            DimensionScore(
                key="mindset",
                name="心态与节奏",
                score=round(mindset_dim, 2),
                reason="平台期稳定性与头部表现",
                weight=0.1,
                level="优势" if mindset_dim >= 65 else "待提升",
                evidence=[f"top10_mean={mean(top10):.2f}", f"ach_std={std_ach:.2f}"],
                indicators={"top10_mean": round(mean(top10), 3), "ach_std": round(std_ach, 3)},
            ),
        ]

        sorted_dims = sorted(dims, key=lambda d: d.score)
        shortfalls = [d.key for d in sorted_dims[:2]]
        strengths = [d.key for d in sorted(dims, key=lambda d: d.score, reverse=True)[:2]]
        radar = RadarOutput(
            player_id=player_id,
            dimensions=dims,
            shortfalls=shortfalls,
            strengths=strengths,
            evaluation_model="s4",
            w_tier=w_tier,
            stage=stage,
        )

        gap_map = {
            "technique_gap": "交互/扫键/折返",
            "accuracy_dx": "准度控制",
            "stamina_base": "体力续航",
            "level_adapt": "14级覆盖",
            "mindset": "平台期心态",
            "rating_w": "阶段策略",
        }
        skill_gaps = [
            SkillGap(
                type=gap_map.get(key, key),
                severity=round(100 - next(d.score for d in dims if d.key == key), 2),
                evidence_songs=profile.titles[:3],
            )
            for key in shortfalls
        ]

        comfort_ceiling = self._percentile(ds_values, 0.80) + 0.25
        foundation_range = self._range(avg_ds - 0.1, avg_ds + 0.5, comfort_ceiling)
        drill_range = self._range(avg_ds - 0.2, avg_ds + 0.7, comfort_ceiling)
        sweep_range = self._range(avg_ds - 0.3, avg_ds + 0.6, comfort_ceiling)
        foundation_strategy = "多打14" if avg_ds >= 13.6 else "扩展目标区间"

        if "level_adapt" in shortfalls or "stamina_base" in shortfalls:
            strategy = TrainingStrategy(
                phase="foundation",
                strategy=foundation_strategy,
                rationale="先扩展当前水平附近的训练覆盖，补齐底力和体力后再冲高定数。",
                target_ds_range=foundation_range,
            )
        elif "technique_gap" in shortfalls:
            strategy = TrainingStrategy(
                phase="drill",
                strategy="专项攻坚",
                rationale="围绕交互/扫键/折返做专项训练，先解决影响最大的技巧短板。",
                target_ds_range=drill_range,
            )
        else:
            strategy = TrainingStrategy(
                phase="sweep_net",
                strategy="收网与大将",
                rationale="先收网吃分，再集中攻克区间大将谱面。",
                target_ds_range=sweep_range,
            )

        level_counts = Counter(profile.level_labels)
        level_profile = {
            "b50_avg_ds": round(mean(ds_values), 4) if ds_values else 0.0,
            "ds_histogram": {
                "lt13": sum(1 for ds in ds_values if ds < 13),
                "13to139": sum(1 for ds in ds_values if 13 <= ds < 14),
                "14to144": sum(1 for ds in ds_values if 14 <= ds <= 14.4),
                "gt145": sum(1 for ds in ds_values if ds > 14.4),
            },
            "level_label_distribution": dict(level_counts),
            "comfort_zone_flag": push_ratio < 0.15,
        }

        dx_profile = {
            "avg_dx_score": round(mean(profile.dx_scores), 2) if profile.dx_scores else 0.0,
            "high_rate_ratio": round(high_rate_ratio, 4),
        }
        return radar, skill_gaps, strategy, level_profile, dx_profile

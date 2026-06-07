from __future__ import annotations

from typing import Any

from app.kb.tagging import suggest_training_tags
from app.models.schemas import AdviceItem, RadarOutput


class AIAdvisor:
    def build_prompt(self, radar: RadarOutput, raw_payload: dict[str, Any]) -> str:
        dim_text = ", ".join(f"{item.name}:{item.score}" for item in radar.dimensions)
        return (
            "你是舞萌训练教练。请根据玩家B50给出分阶段建议。\n"
            f"玩家: {raw_payload.get('nickname', radar.player_id)}\n"
            f"六维: {dim_text}\n"
            f"短板: {','.join(radar.shortfalls)}\n"
            "输出结构: 问题诊断/练习优先级/推荐曲目类别/预计提升区间。"
        )

    async def generate_advice(self, radar: RadarOutput, raw_payload: dict[str, Any]) -> list[AdviceItem]:
        # 首版使用规则引擎兜底，保证离线与无Key时可工作。
        weak_tags = suggest_training_tags(radar.shortfalls)
        player_name = raw_payload.get("nickname", radar.player_id)
        _prompt = self.build_prompt(radar, raw_payload)

        if radar.evaluation_model == "s4":
            return self._generate_s4_advice(radar, player_name, weak_tags)

        return [
            AdviceItem(
                horizon="short",
                title=f"{player_name} 的短期修复重点",
                detail="先优先修复最低两个维度，每天30-45分钟专练同类标签谱面并保留复盘记录。",
                songs=weak_tags[:3],
                target_dimension=radar.shortfalls[0] if radar.shortfalls else None,
                priority=1,
                drill_tags=weak_tags[:3],
                target_ds_range=[13.2, 14.0],
                tone="务实",
            ),
            AdviceItem(
                horizon="middle",
                title="中期提分策略",
                detail="采用 2+1 训练节奏：两天冲高定数，一天做稳定率回收；以周为单位观察B50底部分数抬升。",
                songs=weak_tags[:5],
                target_dimension=radar.shortfalls[1] if len(radar.shortfalls) > 1 else None,
                priority=2,
                drill_tags=weak_tags[:5],
                target_ds_range=[13.5, 14.5],
                tone="策略化",
            ),
            AdviceItem(
                horizon="long",
                title="长期能力构建",
                detail="通过跨风格曲目轮换减少偏科，目标是将六维最低项提升至60分以上后再冲总体Rating。",
                songs=weak_tags,
                target_dimension="all",
                priority=3,
                drill_tags=weak_tags,
                target_ds_range=[13.8, 14.8],
                tone="稳健",
            ),
        ]

    def _generate_s4_advice(self, radar: RadarOutput, player_name: str, weak_tags: list[str]) -> list[AdviceItem]:
        is_w6_or_above = radar.w_tier in {"W6", "万六"}
        short_target = "准度/DX分" if "accuracy_dx" in radar.shortfalls else "14级覆盖"
        short_detail = (
            "先执行“多打14”策略，优先稳定 SSS/SSS+，不要盲目冲更高定数。"
            if not is_w6_or_above
            else "你处于分水岭阶段，先收网后攻大将，先减少失误再追求鸟加。"
        )
        middle_detail = (
            "按“收网与大将”推进：先清理当前区间可吃分谱面，再针对交互/扫键/折返做专项。"
        )
        long_detail = (
            "进入长期期后维持每周节奏：基础日（14级）+专项日（技巧短板）+回收日（准度稳态），接受非线性成长。"
        )
        return [
            AdviceItem(
                horizon="short",
                title=f"{player_name} 的S4短期方案",
                detail=short_detail,
                songs=weak_tags[:3],
                target_dimension=short_target,
                priority=1,
                drill_tags=weak_tags[:3],
                target_ds_range=[13.8, 14.4],
                tone="诊断式",
            ),
            AdviceItem(
                horizon="middle",
                title="中期：收网与专项并行",
                detail=middle_detail,
                songs=weak_tags[:5],
                target_dimension="technique_gap",
                priority=2,
                drill_tags=weak_tags[:5],
                target_ds_range=[13.8, 14.7],
                tone="进阶班",
            ),
            AdviceItem(
                horizon="long",
                title="长期：稳定突破分水岭",
                detail=long_detail,
                songs=weak_tags,
                target_dimension="mindset",
                priority=3,
                drill_tags=weak_tags,
                target_ds_range=[14.0, 14.8],
                tone="关怀式",
            ),
        ]

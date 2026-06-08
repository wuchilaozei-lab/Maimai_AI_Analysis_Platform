from __future__ import annotations

from statistics import mean

from app.analysis.ai_advisor import AIAdvisor
from app.analysis.rating import achievement_for_target_rating, chart_rating
from app.analysis.s4_evaluator import S4Evaluator
from app.analysis.six_dim_engine import SixDimEngine
from app.integrations.diving_fish_client import DivingFishClient
from app.kb.repository import SongRepository
from app.kb.tagging import suggest_training_tags
from app.models.schemas import AnalyzeResponse, B50Item, QueryPlayerRequest, TrainingStrategy


class AnalysisService:
    def __init__(self) -> None:
        self.song_repo = SongRepository()
        self.fish = DivingFishClient()
        self.engine = SixDimEngine(self.song_repo)
        self.s4 = S4Evaluator()
        self.advisor = AIAdvisor()

    async def analyze_b50(self, req: QueryPlayerRequest) -> AnalyzeResponse:
        payload = await self.fish.query_player(req)
        player_id = req.username or req.qq or "unknown"
        records_payload = await self._optional_records_payload(req)
        records_summary = self._build_records_summary(records_payload)

        if req.evaluation_model == "s4":
            radar, skill_gaps, training_strategy, level_profile, dx_profile = self.s4.evaluate(player_id=player_id, payload=payload)
        else:
            radar = self.engine.score(player_id=player_id, payload=payload, records_payload=records_payload)
            skill_gaps = []
            training_strategy = TrainingStrategy(
                phase="legacy",
                strategy="legacy",
                rationale="使用 legacy 六维模型输出建议。",
                target_ds_range=self._target_ds_range_from_payload(payload),
            )
            level_profile = {}
            dx_profile = {}

        advice = await self.advisor.generate_advice(radar, payload)
        b50_items = self._extract_b50(payload)
        b35 = b50_items[:35]
        b15 = b50_items[35:50]
        return AnalyzeResponse(
            player_id=player_id,
            rating=payload.get("rating"),
            evaluation_model=req.evaluation_model,
            w_tier=radar.w_tier,
            stage=radar.stage,
            b50=b50_items,
            b35=b35,
            b15=b15,
            radar=radar,
            advice=advice,
            skill_gaps=skill_gaps,
            training_strategy=training_strategy,
            level_profile=level_profile,
            dx_profile=dx_profile,
            records_summary=records_summary,
            debug={
                "source": "diving-fish",
                "charts_count": len(payload.get("charts", {}).get("sd", [])) + len(payload.get("charts", {}).get("dx", [])),
                "records_enabled": req.include_records,
                "records_count": records_summary.get("total_records", 0),
            },
        )

    @staticmethod
    def _target_ds_range_from_payload(payload: dict) -> list[float]:
        charts = payload.get("charts", {})
        items = (charts.get("sd", []) or []) + (charts.get("dx", []) or [])
        ds_values = [float(item.get("ds", 0.0) or 0.0) for item in items if item.get("ds") is not None]
        if not ds_values:
            return [13.2, 14.0]
        avg_ds = mean(ds_values)
        ceiling = AnalysisService._percentile(ds_values, 0.80) + 0.25
        low = round(max(1.0, avg_ds - 0.3), 1)
        high = round(min(15.0, avg_ds + 0.5, ceiling), 1)
        return [low, max(low, high)]

    @staticmethod
    def _extract_b50(payload: dict) -> list[B50Item]:
        charts = payload.get("charts", {})
        sd = charts.get("sd", []) or []
        dx = charts.get("dx", []) or []
        all_items = sd + dx

        out: list[B50Item] = []
        for idx, item in enumerate(all_items):
            song_id = item.get("song_id")
            cover_url = f"https://www.diving-fish.com/covers/{song_id}.png" if song_id is not None else None
            segment = "B35" if idx < 35 else "B15"
            out.append(
                B50Item(
                    song_id=song_id,
                    title=item.get("title", "unknown"),
                    type=item.get("type"),
                    level_label=item.get("level_label"),
                    ds=item.get("ds"),
                    ra=item.get("ra"),
                    achievements=item.get("achievements"),
                    dx_score=item.get("dxScore"),
                    rate=item.get("rate"),
                    fc=item.get("fc"),
                    fs=item.get("fs"),
                    cover_url=cover_url,
                    segment=segment,
                )
            )
        return out

    async def _optional_records_payload(self, req: QueryPlayerRequest) -> dict | None:
        if not req.include_records:
            return None
        try:
            return await self.fish.player_records(import_token=req.import_token)
        except Exception:
            return None

    @staticmethod
    def _build_records_summary(records_payload: dict | None) -> dict:
        if not records_payload:
            return {}
        records = records_payload.get("records", []) or []
        if not records:
            return {"total_records": 0}

        def is_fc(item: dict) -> bool:
            return str(item.get("fc", "")).lower() in {"fc", "fcp", "ap", "app"}

        ds_values = [float(item.get("ds", 0.0) or 0.0) for item in records]
        level_histogram = {"lt13": 0, "13to139": 0, "14to144": 0, "gt145": 0}
        for ds in ds_values:
            if ds < 13:
                level_histogram["lt13"] += 1
            elif ds < 14:
                level_histogram["13to139"] += 1
            elif ds <= 14.4:
                level_histogram["14to144"] += 1
            else:
                level_histogram["gt145"] += 1

        return {
            "total_records": len(records),
            "fc_count": sum(1 for item in records if is_fc(item)),
            "level_histogram": level_histogram,
        }

    def recommend_songs_by_shortfall(self, shortfalls: list[str], limit: int = 6):
        return self.recommend_songs(shortfalls=shortfalls, limit=limit)

    def recommend_songs(
        self,
        shortfalls: list[str],
        limit: int = 6,
        b50_items: list[B50Item] | None = None,
        target_ds_range: list[float] | None = None,
    ):
        if self.song_repo.using_seed_data:
            return []
        tags = suggest_training_tags(shortfalls)
        b50_items = b50_items or []
        played_keys = {
            (item.song_id, (item.level_label or "").lower(), (item.type or "").lower())
            for item in b50_items
            if item.song_id is not None
        }
        b50_ds = [float(item.ds) for item in b50_items if item.ds is not None]

        if target_ds_range and len(target_ds_range) >= 2:
            min_ds, max_ds = float(target_ds_range[0]), float(target_ds_range[1])
        else:
            avg_ds = mean(b50_ds) if b50_ds else 13.5
            min_ds, max_ds = max(1.0, avg_ds - 0.3), min(15.0, avg_ds + 0.5)
        if b50_ds:
            # 推荐上沿不能只看策略区间；用B50高位定数估计“能练但不离谱”的天花板。
            max_ds = max(min_ds, min(max_ds, self._percentile(b50_ds, 0.80) + 0.25))
        target_mid = (min_ds + max_ds) / 2

        tag_pairs = {tuple(tag.split(":", 1)) for tag in tags if ":" in tag}
        current_achievements = [float(item.achievements) for item in b50_items if item.achievements is not None]
        expected_achievement = min(100.5, max(97.0, (mean(current_achievements) if current_achievements else 98.0) + 0.25))
        attainable_achievement = min(100.5, expected_achievement + 0.55)
        b35_ra = [int(item.ra) for item in b50_items if item.segment == "B35" and item.ra is not None]
        b15_ra = [int(item.ra) for item in b50_items if item.segment == "B15" and item.ra is not None]
        all_ra = [int(item.ra) for item in b50_items if item.ra is not None]
        b35_border = min(b35_ra) if len(b35_ra) >= 35 else (min(all_ra) if all_ra else 0)
        b15_border = min(b15_ra) if len(b15_ra) >= 15 else (min(all_ra) if all_ra else 0)
        global_border = min(all_ra) if len(all_ra) >= 50 else min(b35_border or 0, b15_border or 0)

        scored = []
        for song in self.song_repo.filter_by_ds(min_ds=min_ds, max_ds=max_ds):
            difficulty_type = song.difficulty.split("-", 1)[0].lower() if "-" in song.difficulty else ""
            song_key = (song.song_id, song.level.lower(), difficulty_type)
            if song_key in played_keys:
                continue

            song_tags = {(tag.key, tag.value) for tag in song.tags}
            tag_score = len(song_tags & tag_pairs) * 10
            distance_score = max(0.0, 6.0 - abs(song.ds - target_mid) * 4)
            difficulty_score = 2 if any(name in song.difficulty.lower() for name in ["master", "re:master"]) else 0
            expected_ra = chart_rating(song.ds, expected_achievement)
            border = b15_border if self._looks_like_current_version(song) else b35_border
            border = border or global_border
            ra_margin = expected_ra - border
            rating_score = max(-8.0, min(18.0, ra_margin / 2))
            needed_achievement = achievement_for_target_rating(song.ds, border + 1) if border else None
            if border and (needed_achievement is None or needed_achievement > attainable_achievement):
                continue
            attainability_score = 0.0
            if needed_achievement is not None:
                attainability_score = max(-6.0, min(8.0, (expected_achievement - needed_achievement) * 2.5))

            score = tag_score + distance_score + difficulty_score + rating_score + attainability_score
            if score <= 0:
                continue
            scored.append((
                score,
                -expected_ra,
                abs(song.ds - target_mid),
                needed_achievement if needed_achievement is not None else 999.0,
                song.title,
                song.difficulty,
                song,
            ))

        scored.sort(key=lambda item: (-item[0], item[1], item[2], item[3], item[4], item[5]))

        results = []
        seen_chart_keys = set()
        for *_unused, song in scored:
            chart_key = (song.song_id, song.difficulty)
            if chart_key in seen_chart_keys:
                continue
            seen_chart_keys.add(chart_key)
            results.append(song)
            if len(results) >= limit:
                break
        # 不再“补齐”随机曲，避免看起来像虚构推荐；不足就按实际返回。
        return results

    @staticmethod
    def _looks_like_current_version(song) -> bool:
        current_markers = {"buddies", "prism", "current", "新版本"}
        version = song.version.lower()
        return any(marker in version for marker in current_markers)

    @staticmethod
    def _percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
        return ordered[idx]

    async def ensure_music_data_ready(self) -> tuple[bool, str | None]:
        if self.song_repo.using_music_data:
            return True, None
        try:
            music_data = await self.fish.music_data()
            count = self.song_repo.upsert_from_music_data(music_data)
            if count <= 0:
                return False, "曲库同步结果为空，已阻断推荐。"
            return True, None
        except Exception as exc:
            return False, f"曲库同步失败：{exc}"

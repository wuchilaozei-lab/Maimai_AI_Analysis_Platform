from __future__ import annotations

from app.analysis.ai_advisor import AIAdvisor
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
            radar = self.engine.score(player_id=player_id, payload=payload)
            skill_gaps = []
            training_strategy = TrainingStrategy(
                phase="legacy",
                strategy="legacy",
                rationale="使用 legacy 六维模型输出建议。",
                target_ds_range=[13.2, 14.8],
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
        tags = suggest_training_tags(shortfalls)
        results = []
        seen_ids = set()
        for tag in tags:
            songs = self.song_repo.filter_by_tags([tag])
            for song in songs:
                if song.song_id in seen_ids:
                    continue
                seen_ids.add(song.song_id)
                results.append(song)
                if len(results) >= limit:
                    return results
        if len(results) < limit:
            for song in self.song_repo.list_all():
                if song.song_id in seen_ids:
                    continue
                results.append(song)
                if len(results) >= limit:
                    break
        return results

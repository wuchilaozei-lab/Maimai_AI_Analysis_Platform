from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.integrations.diving_fish_client import DivingFishError
from app.models.schemas import AnalyzeResponse, QueryPlayerRequest
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])
service = AnalysisService()


@router.post("/b50", response_model=AnalyzeResponse)
async def analyze_b50(req: QueryPlayerRequest) -> AnalyzeResponse:
    try:
        return await service.analyze_b50(req)
    except DivingFishError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommend")
async def recommend_from_player(req: QueryPlayerRequest) -> dict:
    music_ready, music_warning = await service.ensure_music_data_ready()
    try:
        analyzed = await service.analyze_b50(req)
        shortfalls = analyzed.radar.shortfalls
        player_id = analyzed.player_id
        w_tier = analyzed.w_tier
        strategy = analyzed.training_strategy.model_dump() if analyzed.training_strategy else None
        target_ds_range = analyzed.training_strategy.target_ds_range if analyzed.training_strategy else None
        b50_items = analyzed.b50
        source = "player-shortfall"
        warning = None
    except DivingFishError as exc:
        if req.evaluation_model == "s4":
            shortfalls = ["level_adapt", "technique_gap"]
            target_ds_range = [13.8, 14.4]
        else:
            shortfalls = ["coverage", "resilience"]
            target_ds_range = [13.2, 14.0]
        player_id = req.username or req.qq or "unknown"
        w_tier = None
        strategy = None
        b50_items = []
        source = "fallback-default"
        warning = str(exc)

    if not music_ready:
        items = []
        warning = f"{warning}；{music_warning}" if warning else music_warning
        source = "blocked-no-music-data"
    else:
        items = service.recommend_songs(
            shortfalls=shortfalls,
            limit=6,
            b50_items=b50_items,
            target_ds_range=target_ds_range,
        )
        if not items:
            warning = f"{warning}；真实曲库命中不足" if warning else "真实曲库命中不足"
    return {
        "player_id": player_id,
        "evaluation_model": req.evaluation_model,
        "w_tier": w_tier,
        "shortfalls": shortfalls,
        "strategy": strategy,
        "target_ds_range": target_ds_range,
        "items": [item.model_dump() for item in items],
        "source": source,
        "warning": warning,
    }

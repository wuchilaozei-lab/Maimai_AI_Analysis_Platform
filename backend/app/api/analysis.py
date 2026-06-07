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
    try:
        analyzed = await service.analyze_b50(req)
        shortfalls = analyzed.radar.shortfalls
        player_id = analyzed.player_id
        w_tier = analyzed.w_tier
        strategy = analyzed.training_strategy.model_dump() if analyzed.training_strategy else None
        source = "player-shortfall"
        warning = None
    except DivingFishError as exc:
        if req.evaluation_model == "s4":
            shortfalls = ["level_adapt", "technique_gap"]
        else:
            shortfalls = ["coverage", "resilience"]
        player_id = req.username or req.qq or "unknown"
        w_tier = None
        strategy = None
        source = "fallback-default"
        warning = str(exc)

    items = service.recommend_songs_by_shortfall(shortfalls, limit=6)
    return {
        "player_id": player_id,
        "evaluation_model": req.evaluation_model,
        "w_tier": w_tier,
        "shortfalls": shortfalls,
        "strategy": strategy,
        "items": [item.model_dump() for item in items],
        "source": source,
        "warning": warning,
    }

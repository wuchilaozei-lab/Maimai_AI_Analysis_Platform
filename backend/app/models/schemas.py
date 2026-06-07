from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryPlayerRequest(BaseModel):
    username: str | None = None
    qq: str | None = None
    b50: str = "1"
    evaluation_model: Literal["legacy", "s4"] = "legacy"
    include_records: bool = False
    import_token: str | None = None


class TokenSetRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class SongTag(BaseModel):
    key: str
    value: str


class SongEntry(BaseModel):
    song_id: int
    title: str
    version: str
    difficulty: str
    level: str
    ds: float
    charter: str = "unknown"
    tags: list[SongTag] = Field(default_factory=list)


class DimensionScore(BaseModel):
    key: str
    name: str
    score: float
    reason: str
    weight: float | None = None
    level: str | None = None
    evidence: list[str] = Field(default_factory=list)
    indicators: dict[str, float] = Field(default_factory=dict)


class RadarOutput(BaseModel):
    player_id: str
    dimensions: list[DimensionScore]
    shortfalls: list[str]
    strengths: list[str]
    evaluation_model: Literal["legacy", "s4"] = "legacy"
    w_tier: str | None = None
    stage: str | None = None


class AdviceItem(BaseModel):
    horizon: Literal["short", "middle", "long"]
    title: str
    detail: str
    songs: list[str] = Field(default_factory=list)
    target_dimension: str | None = None
    priority: int | None = None
    drill_tags: list[str] = Field(default_factory=list)
    target_ds_range: list[float] = Field(default_factory=list)
    tone: str | None = None


class B50Item(BaseModel):
    song_id: int | None = None
    title: str
    type: str | None = None
    level_label: str | None = None
    ds: float | None = None
    ra: int | None = None
    achievements: float | None = None
    dx_score: int | None = None
    rate: str | None = None
    fc: str | None = None
    fs: str | None = None
    cover_url: str | None = None
    segment: Literal["B35", "B15"] | None = None


class SkillGap(BaseModel):
    type: str
    severity: float
    evidence_songs: list[str] = Field(default_factory=list)


class TrainingStrategy(BaseModel):
    phase: str
    rationale: str
    target_ds_range: list[float] = Field(default_factory=list)
    strategy: str | None = None


class AnalyzeResponse(BaseModel):
    player_id: str
    rating: int | None = None
    evaluation_model: Literal["legacy", "s4"] = "legacy"
    w_tier: str | None = None
    stage: str | None = None
    b50: list[B50Item] = Field(default_factory=list)
    b35: list[B50Item] = Field(default_factory=list)
    b15: list[B50Item] = Field(default_factory=list)
    radar: RadarOutput
    advice: list[AdviceItem]
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    training_strategy: TrainingStrategy | None = None
    level_profile: dict[str, Any] = Field(default_factory=dict)
    dx_profile: dict[str, Any] = Field(default_factory=dict)
    records_summary: dict[str, Any] = Field(default_factory=dict)
    debug: dict[str, Any] = Field(default_factory=dict)

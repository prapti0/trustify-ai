from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DetectorOutcome:
    module: str
    status: str  # completed | unavailable | failed
    finding_label: str | None = None
    confidence: float | None = None
    model_name: str | None = None
    model_version: str | None = None
    limitations: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class VisualDetectionBundle:
    outcomes: list[DetectorOutcome]
    content_stage: tuple[str, str]
    ai_stage: tuple[str, str]
    forensics_stage: tuple[str, str]
    ai_generation: dict
    manipulation: dict
    classification_hint: str | None  # low|medium|high|inconclusive|None

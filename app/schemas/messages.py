"""Structured agent analysis. JSON is the internal form."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CLAIM_LABELS = (
    "FACT",
    "ESTIMATE",
    "ASSUMPTION",
    "UNKNOWN",
    "DISPROVEN",
    "INFERENCE",
    "OPINION",
)

EVIDENCE_LEVELS: dict[int, str] = {
    1: "Customer payment",
    2: "Actual usage",
    3: "Retention",
    4: "Repeat purchase",
    5: "Referral",
    6: "Paid pilot",
    7: "Observed customer behavior",
    8: "Customer interview",
    9: "First-party data",
    10: "Primary sources",
    11: "Reliable datasets",
    12: "Expert analysis",
    13: "Secondary research",
    14: "Social signals",
    15: "AI reasoning",
    16: "Founder assumption",
}

CONFIDENCE_LEVELS = ("low", "medium", "high")

_STRING_LIST_FIELDS = (
    "assumptions",
    "unknowns",
    "disagreements",
    "counterarguments",
    "risks",
    "opportunities",
)


@dataclass(frozen=True)
class LabeledClaim:
    text: str
    label: str


@dataclass(frozen=True)
class EvidenceItem:
    text: str
    level: int


@dataclass(frozen=True)
class Source:
    title: str
    locator: str
    source_type: str


@dataclass(frozen=True)
class AgentAnalysis:
    thesis: str
    facts: tuple[LabeledClaim, ...]
    evidence: tuple[EvidenceItem, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    disagreements: tuple[str, ...]
    counterarguments: tuple[str, ...]
    risks: tuple[str, ...]
    opportunities: tuple[str, ...]
    recommendation: str
    confidence: str
    what_would_change_my_mind: str
    sources: tuple[Source, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analysis_json_schema() -> dict[str, Any]:
    """JSON Schema sent as OpenAI Responses text.format.schema."""
    claim = _object_schema(
        {
            "text": {"type": "string"},
            "label": {"type": "string", "enum": list(CLAIM_LABELS)},
        }
    )
    evidence = _object_schema(
        {
            "text": {"type": "string"},
            "level": {"type": "integer"},
        }
    )
    source = _object_schema(
        {
            "title": {"type": "string"},
            "locator": {"type": "string"},
            "source_type": {"type": "string"},
        }
    )
    string_array = {"type": "array", "items": {"type": "string"}}
    return _object_schema(
        {
            "thesis": {"type": "string"},
            "facts": {"type": "array", "items": claim},
            "evidence": {"type": "array", "items": evidence},
            "assumptions": string_array,
            "unknowns": string_array,
            "disagreements": string_array,
            "counterarguments": string_array,
            "risks": string_array,
            "opportunities": string_array,
            "recommendation": {"type": "string"},
            "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
            "what_would_change_my_mind": {"type": "string"},
            "sources": {"type": "array", "items": source},
        }
    )


def parse_agent_analysis(payload: dict[str, Any]) -> AgentAnalysis:
    if not isinstance(payload, dict):
        raise ValueError("Analysis must be a JSON object")
    expected = set(analysis_json_schema()["properties"])
    missing = expected.difference(payload)
    unknown = set(payload).difference(expected)
    if missing or unknown:
        raise ValueError(f"Analysis keys mismatch. missing={sorted(missing)} unknown={sorted(unknown)}")

    thesis = _required_text(payload, "thesis")
    recommendation = _required_text(payload, "recommendation")
    change = _required_text(payload, "what_would_change_my_mind")
    confidence = payload["confidence"]
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError("confidence must be low, medium, or high")

    return AgentAnalysis(
        thesis=thesis,
        facts=tuple(_parse_claim(item) for item in _array(payload, "facts")),
        evidence=tuple(_parse_evidence(item) for item in _array(payload, "evidence")),
        assumptions=_string_tuple(payload, "assumptions"),
        unknowns=_string_tuple(payload, "unknowns"),
        disagreements=_string_tuple(payload, "disagreements"),
        counterarguments=_string_tuple(payload, "counterarguments"),
        risks=_string_tuple(payload, "risks"),
        opportunities=_string_tuple(payload, "opportunities"),
        recommendation=recommendation,
        confidence=confidence,
        what_would_change_my_mind=change,
        sources=tuple(_parse_source(item) for item in _array(payload, "sources")),
    )


def render_analysis(analysis: AgentAnalysis) -> str:
    lines = [
        f"Thesis: {analysis.thesis}",
        f"Confidence: {analysis.confidence}",
        f"Recommendation: {analysis.recommendation}",
        f"What would change my mind: {analysis.what_would_change_my_mind}",
    ]
    return "\n".join(lines)


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _array(payload: dict[str, Any], name: str) -> list[Any]:
    value = payload[name]
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _string_tuple(payload: dict[str, Any], name: str) -> tuple[str, ...]:
    if name not in _STRING_LIST_FIELDS:
        raise ValueError(name)
    values = _array(payload, name)
    cleaned: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name} entries must be non-empty strings")
        cleaned.append(item.strip())
    return tuple(cleaned)


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload[name]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _parse_claim(item: Any) -> LabeledClaim:
    if not isinstance(item, dict):
        raise ValueError("fact must be an object")
    text = item.get("text")
    label = item.get("label")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("fact text must be a non-empty string")
    if label not in CLAIM_LABELS:
        raise ValueError("fact label is not a recognized claim class")
    return LabeledClaim(text=text.strip(), label=label)


def _parse_evidence(item: Any) -> EvidenceItem:
    if not isinstance(item, dict):
        raise ValueError("evidence must be an object")
    text = item.get("text")
    level = item.get("level")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("evidence text must be a non-empty string")
    if isinstance(level, bool) or not isinstance(level, int) or level not in EVIDENCE_LEVELS:
        raise ValueError("evidence level must be an integer from 1 to 16")
    return EvidenceItem(text=text.strip(), level=level)


def _parse_source(item: Any) -> Source:
    if not isinstance(item, dict):
        raise ValueError("source must be an object")
    title = item.get("title")
    locator = item.get("locator")
    source_type = item.get("source_type")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("source title must be a non-empty string")
    if not isinstance(locator, str):
        raise ValueError("source locator must be a string")
    if not isinstance(source_type, str) or not source_type.strip():
        raise ValueError("source type must be a non-empty string")
    return Source(title=title.strip(), locator=locator.strip(), source_type=source_type.strip())

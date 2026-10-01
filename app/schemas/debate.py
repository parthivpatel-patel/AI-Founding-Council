"""Cross-examination schema and local disagreement detection.

Agreement among models is not evidence. This module does not vote.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Disagreement:
    claim: str
    sides: str
    why: str


@dataclass(frozen=True)
class CrossExamination:
    agreements: tuple[str, ...]
    disagreements: tuple[Disagreement, ...]
    unsupported_claims: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    contradictory_assumptions: tuple[str, ...]
    overlooked_risks: tuple[str, ...]
    new_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Dispute:
    dispute_id: str
    claim: str
    raised_by: tuple[str, ...]
    sides: str
    why: str
    status: str
    evidence: str
    required_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_FIELDS = (
    "agreements",
    "disagreements",
    "unsupported_claims",
    "missing_evidence",
    "contradictory_assumptions",
    "overlooked_risks",
    "new_questions",
)

_STRING_FIELDS = (
    "agreements",
    "unsupported_claims",
    "missing_evidence",
    "contradictory_assumptions",
    "overlooked_risks",
    "new_questions",
)


def cross_examination_schema() -> dict[str, Any]:
    disagreement = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "claim": {"type": "string"},
            "sides": {"type": "string"},
            "why": {"type": "string"},
        },
        "required": ["claim", "sides", "why"],
    }
    string_array = {"type": "array", "items": {"type": "string"}}
    properties = {name: string_array for name in _STRING_FIELDS}
    properties["disagreements"] = {"type": "array", "items": disagreement}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(_FIELDS),
    }


def parse_cross_examination(payload: dict[str, Any]) -> CrossExamination:
    if not isinstance(payload, dict):
        raise ValueError("Cross-examination must be a JSON object")
    expected = set(_FIELDS)
    missing = expected.difference(payload)
    unknown = set(payload).difference(expected)
    if missing or unknown:
        raise ValueError(f"Cross-examination keys mismatch. missing={sorted(missing)} unknown={sorted(unknown)}")
    return CrossExamination(
        agreements=_strings(payload, "agreements"),
        disagreements=tuple(_disagreement(item) for item in _array(payload, "disagreements")),
        unsupported_claims=_strings(payload, "unsupported_claims"),
        missing_evidence=_strings(payload, "missing_evidence"),
        contradictory_assumptions=_strings(payload, "contradictory_assumptions"),
        overlooked_risks=_strings(payload, "overlooked_risks"),
        new_questions=_strings(payload, "new_questions"),
    )


def detect_disputes(reviews: list[tuple[str, CrossExamination]]) -> list[Dispute]:
    """Group explicit disagreements. Identical claims become one dispute, not a vote."""
    grouped: dict[str, list[tuple[str, Disagreement]]] = {}
    for role, review in reviews:
        for item in review.disagreements:
            key = " ".join(item.claim.lower().split())
            grouped.setdefault(key, []).append((role, item))
    disputes: list[Dispute] = []
    for index, rows in enumerate(grouped.values(), start=1):
        claim = rows[0][1].claim
        disputes.append(
            Dispute(
                dispute_id=f"DISPUTE-{index:03d}",
                claim=claim,
                raised_by=tuple(role for role, _item in rows),
                sides=" | ".join(f"{role}: {item.sides}" for role, item in rows),
                why=" | ".join(f"{role}: {item.why}" for role, item in rows),
                status="UNVERIFIED",
                evidence="Insufficient. A cross-examination named this dispute. It is not resolved.",
                required_action="Research required.",
            )
        )
    return disputes


def _array(payload: dict[str, Any], name: str) -> list[Any]:
    value = payload[name]
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _strings(payload: dict[str, Any], name: str) -> tuple[str, ...]:
    cleaned: list[str] = []
    for item in _array(payload, name):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name} entries must be non-empty strings")
        cleaned.append(item.strip())
    return tuple(cleaned)


def _disagreement(item: Any) -> Disagreement:
    if not isinstance(item, dict):
        raise ValueError("disagreement must be an object")
    claim = item.get("claim")
    sides = item.get("sides")
    why = item.get("why")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("disagreement claim must be a non-empty string")
    if not isinstance(sides, str) or not sides.strip():
        raise ValueError("disagreement sides must be a non-empty string")
    if not isinstance(why, str) or not why.strip():
        raise ValueError("disagreement why must be a non-empty string")
    return Disagreement(claim=claim.strip(), sides=sides.strip(), why=why.strip())

"""CEO decision memo schema. The human CEO is the only approver."""

from __future__ import annotations

from dataclasses import dataclass

CEO_GATED_ACTIONS = (
    "spending_money",
    "paid_api_usage",
    "signing_contracts",
    "legal_commitment",
    "contacting_customers",
    "customer_promise",
    "strategic_pivot",
    "regulated_activity",
    "financial_transaction",
    "production_deployment",
    "data_deletion",
    "hiring",
    "major_partnership",
    "pricing_change",
    "significant_liability",
)


@dataclass(frozen=True)
class DecisionMemo:
    question: str
    current_state: str
    what_we_know: str
    what_we_dont_know: str
    strongest_evidence: str
    strongest_counterargument: str
    key_assumptions: str
    critical_risks: str
    council_disagreements: str
    cheapest_experiment: str
    expected_cost: str
    expected_learning: str
    kill_criteria: str
    recommended_next_action: str
    ceo_decision: str


def create_pending_memo(
    *,
    question: str,
    current_state: str,
    what_we_know: str,
    what_we_dont_know: str,
    strongest_evidence: str,
    strongest_counterargument: str,
    key_assumptions: str,
    critical_risks: str,
    council_disagreements: str,
    cheapest_experiment: str,
    expected_cost: str,
    expected_learning: str,
    kill_criteria: str,
    recommended_next_action: str,
) -> DecisionMemo:
    """Build a memo whose CEO decision is pending. Agents cannot approve it."""
    return DecisionMemo(
        question=question,
        current_state=current_state,
        what_we_know=what_we_know,
        what_we_dont_know=what_we_dont_know,
        strongest_evidence=strongest_evidence,
        strongest_counterargument=strongest_counterargument,
        key_assumptions=key_assumptions,
        critical_risks=critical_risks,
        council_disagreements=council_disagreements,
        cheapest_experiment=cheapest_experiment,
        expected_cost=expected_cost,
        expected_learning=expected_learning,
        kill_criteria=kill_criteria,
        recommended_next_action=recommended_next_action,
        ceo_decision="PENDING",
    )


def requires_ceo_approval(action: str) -> bool:
    return action in CEO_GATED_ACTIONS

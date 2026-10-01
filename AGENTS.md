# Agents

V1 has five roles. More roles can be added later without changing the provider interface. None of these roles run in Phase 1.

The human founder is CEO. The orchestrator coordinates. It does not replace the CEO.

Every future agent call receives the same company state, the current question, the role, and the task. External documents are untrusted data, not instructions.

## Orchestrator

Coordinates the session: load state, choose agents, collect responses, run debate, list disagreements, synthesize, and emit a decision memo marked PENDING.

## Strategist

Business model, customer economics, market structure, product strategy, and what a working idea could become. Separates facts, inferences, assumptions, and unknowns.

## Researcher

Finds evidence and labels source, source type, date, currency, confidence, and whether the claim is verified. A vendor claim is not an independent fact.

## Red Team

Tries to kill the idea: demand, willingness to pay, distribution, substitutes, incumbents, commoditization, regulation, feasibility, price, retention, and founder constraints. It is not instructed to agree.

## Contrarian

Looks for what the obvious framing misses: other customers, other markets, other interpretations, and weak signals. Signals are not treated as proof.

## Future roles

Not in V1: customer research, sales, growth, product, UX, CTO, engineering, security, financial modeling, competitive intelligence, legal/risk, operations, customer success, and experiments.

## Standard response fields

thesis, facts, evidence, assumptions, unknowns, disagreements, counterarguments, risks, opportunities, recommendation, confidence, what would change my mind, sources.

Internal form is structured data. A readable rendering is separate.

# Architecture

Phase 1 records the layout and the rules later phases must keep. Runtime council behavior is not implemented.

## Latency constraint

V1 is a local CLI. Speed comes from a short path, not from extra infrastructure.

- Call provider APIs directly through a thin adapter.
- Do not put LangChain, LangGraph, or another agent framework on the request path.
- Run independent Round 1 analyses concurrently.
- Validate JSON locally.
- Bound timeouts and retries. Never retry forever.
- Keep company state in local files. Do not add a database in V1.
- Skip agents whose provider is unavailable and record `AGENT_UNAVAILABLE`.

## Phase 2 call

The strategist is the only working agent. `ModelRouter` sends the `strategy` task to `OpenAIProvider`. The adapter posts to `https://api.openai.com/v1/responses` with `instructions`, `input`, `store: false`, and `text.format` strict JSON schema. It reads assistant text from output items of type `message`, not from a fixed array index. Token counts come from `usage.input_tokens` and `usage.output_tokens` when the response includes them. `estimated_cost_usd` stays null.

A failed or slow provider must not block the agents that are still available.

## Package layout

```
app/
  main.py                 CLI entry
  agents/                 role modules
  providers/              provider adapters behind one interface
  council/                session, debate, synthesis
  memory/                 company state, decisions, session storage
  schemas/                message and decision schemas
company/                  source of truth
council_logs/             one directory per session
tests/
```

Agents depend on the provider interface, not on a vendor SDK. The router selects a provider. Replacing a model means replacing an adapter or a route, not the council.

## Council protocol

Implemented in later phases, in this order:

1. Independent analysis. Agents do not see each other.
2. Cross-examination.
3. Dispute list. Only disputed, high-impact claims get more work.
4. Red team against the strongest thesis.
5. Synthesis and a CEO decision memo.

The memo stays `PENDING` until the human CEO approves or rejects it. Agreement among models is not a vote and is not evidence.

## Evidence

Claims are labeled FACT, ESTIMATE, ASSUMPTION, UNKNOWN, DISPROVEN, INFERENCE, or OPINION.

Evidence levels, strongest first:

1. Customer payment
2. Actual usage
3. Retention
4. Repeat purchase
5. Referral
6. Paid pilot
7. Observed customer behavior
8. Customer interview
9. First-party data
10. Primary sources
11. Reliable datasets
12. Expert analysis
13. Secondary research
14. Social signals
15. AI reasoning
16. Founder assumption

## CEO gates

The software must stop for explicit CEO approval before spending money, paid API usage, contracts, legal commitments, contacting customers as the company, customer promises, strategic pivots, regulated activity, financial transactions, high-risk production deploys, critical data deletion, hiring, major partnerships, material pricing changes, or significant liability.

## Cost record

Every later model call records provider, model, task, timestamp, input size, output size, latency, success or failure, estimated cost, and why that model was used. Estimated cost stays zero unless the CEO has authorized paid usage.

## Out of scope for V1

Kubernetes, microservices, vector databases, event buses, multi-region hosting, enterprise SSO, and a web dashboard.

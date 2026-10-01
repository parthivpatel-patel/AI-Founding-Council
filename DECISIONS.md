# Architecture decisions

## ADR-001 — Local files, one process

V1 runs as a local Python process. Company memory is Markdown in `company/`. Session logs go to `council_logs/`. This keeps the system auditable and avoids network hops that V1 does not need.

## ADR-002 — Thin provider calls

The hot path is `agent -> router -> provider adapter -> official API`. No agent framework sits in front of the model. Independent analyses run concurrently once providers exist. This is the latency rule for every later phase.

## ADR-003 — Secrets only in the environment

API keys live in `.env`, which is gitignored. `.env.example` has empty values. Prompts and logs must not include secrets.

## ADR-004 — CEO remains the decision maker

Decision memos are created as `PENDING`. Agents cannot spend money, contact customers, or take irreversible actions. Paid API usage requires CEO authorization. The AI infrastructure budget starts at $0.

## ADR-005 — One provider before four

The first working milestone is one verified provider and one agent. Remaining providers are added only after that path saves a structured response. Free tier, quota, and price are verified at connection time, not assumed.

## ADR-006 — Stubs are not implementations

A module is implemented only when tests show that behavior. Synthesis is still a stub.

## ADR-007 — No invented price

Estimated cost stays null until a price table is verified. A call is not sent unless that provider's authorization flag is set. Malformed output is saved as a failure and is not sent back to the model.

## ADR-008 — Four independent calls, six swappable providers

Round 1 runs the strategist, researcher, red team, and contrarian at the same time. None of them receives another agent's answer. The default routes are OpenAI, Gemini, Anthropic, and xAI. NVIDIA NIM and the Cursor agent SDK are adapters a role can opt into. A missing or unauthorized provider is recorded as `AGENT_UNAVAILABLE` and does not cancel the other calls.

## ADR-009 — Cross-examination is not a vote

Round 2 runs only for agents that finished round 1. Each one sees the other round-1 analyses and none of the round-2 answers. Disputes are created only from disagreements an agent explicitly states. Matching claims are merged into one `UNVERIFIED` dispute. An empty dispute list means no disagreement was stated. It does not mean the claim is true. Cursor is the default CTO provider.

## ADR-010 — The memo stays pending

Evidence resolution runs only for stated disputes and cannot mark them resolved. One red-team pass attacks the strategist thesis when that agent answered, otherwise the first thesis that exists. Agreement is not the selection rule. The decision memo is assembled from those records with `create_pending_memo`. Company state and the decision log stay unchanged.

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

A module is implemented only when tests show that behavior. Anthropic, Gemini, xAI, debate, and synthesis are still stubs.

## ADR-007 — One OpenAI call, no invented price

The strategist calls OpenAI through `POST https://api.openai.com/v1/responses` with `store` set to false and a strict JSON schema. The model id comes from `OPENAI_MODEL`. The call is not sent unless `OPENAI_API_AUTHORIZED=1`. Estimated cost stays null until a price table is verified. Malformed output is saved as a failure and is not sent back to the model, because a second call would spend quota again.

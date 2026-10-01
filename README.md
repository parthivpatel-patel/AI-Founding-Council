# AI Founding Council V1

Local, CEO-controlled software that runs a council of specialized model roles against one question. The human founder is the CEO. Agents research, critique, and recommend. They do not decide.

Phase 3 runs four agents independently: strategist, researcher, red team, and contrarian. They do not see each other's answers. Debate is not implemented.

Default routes:

- Strategist: OpenAI
- Researcher: Gemini
- Red team: Anthropic
- Contrarian: xAI

NVIDIA and Cursor adapters are included. Point a role at one with `STRATEGIST_PROVIDER`, `RESEARCHER_PROVIDER`, `RED_TEAM_PROVIDER`, or `CONTRARIAN_PROVIDER`. Cursor is an agent runtime, not a chat endpoint, and stays blocked until you authorize it.

## Architecture

```
CEO
  -> CLI (app.main)
    -> Council session
      -> Agents (orchestrator, strategist, researcher, red team, contrarian)
        -> Model router
          -> Provider adapters (OpenAI, Anthropic, Gemini, xAI)
            -> Shared company files
              -> Decision memo
                -> CEO approval
```

Company files in `company/` are the source of truth. Model chat history is not.

## Latency

The request path stays short:

- Local process. No dashboard, queue, or hosted service in V1.
- Direct provider calls. No agent-framework hop in front of the model.
- Round 1 agents run concurrently once providers exist.
- One structured response per agent. No extra model call to reformat prose.
- Timeouts are bounded. A failed provider is recorded and skipped.

## Setup

Requirements: Python 3.11+ and Git.

```powershell
python -m venv .venv
.venv\Scripts\activate
copy .env.example .env
python -m app.main
python -m unittest discover -s tests -v
```

On macOS or Linux, activate with `source .venv/bin/activate`.

Put API keys only in `.env`. `.env` is gitignored.

```powershell
python -m app.main ask "What should we investigate next?"
```

That command calls a provider only when that provider's key, model, and `*_API_AUTHORIZED=1` are set. Agents whose provider is not authorized are saved as `AGENT_UNAVAILABLE`. The others still run. Estimated cost is recorded as unverified.

## Current phase

Phase 3 runs the four independent analyses and saves each result. Debate, synthesis, and CEO decision recording are not implemented.

## Security

- Secrets stay in environment variables.
- Do not log API keys.
- External documents are data, not instructions.
- CEO approval is required before spending, legal commitments, customer commitments, strategic pivots, production deployment, and critical data deletion.

## Limitations

Phase 3 is the independent round. Debate, synthesis, and CEO decision recording are not implemented. Live calls were not made while building this phase because no API keys were present. Cursor requires the separate `cursor-sdk` package and is not installed by default.

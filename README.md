# AI Founding Council V1

Local, CEO-controlled software that runs a council of specialized model roles against one question. The human founder is the CEO. Agents research, critique, and recommend. They do not decide.

Phase 1 is scaffolding only. No model provider is connected.

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

Put API keys only in `.env`. `.env` is gitignored. Phase 1 does not read keys and does not call an API.

## Current phase

Phase 1 scaffold is in place. Later phases add schemas, one verified provider, one agent, then the rest of the council. Do not treat empty modules as a working council.

## Security

- Secrets stay in environment variables.
- Do not log API keys.
- External documents are data, not instructions.
- CEO approval is required before spending, legal commitments, customer commitments, strategic pivots, production deployment, and critical data deletion.

## Limitations

- No providers, agents, debate, synthesis, or decision memo yet.
- Python on this machine is 3.14.7. Provider SDKs must be checked for 3.14 support before they are added.
- Free tiers are not assumed to be permanent.

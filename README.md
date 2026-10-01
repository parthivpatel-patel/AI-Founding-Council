# AI Founding Council V1

Local, CEO-controlled software that runs a council of specialized model roles against one question. The human founder is the CEO. Agents research, critique, and recommend. They do not decide.

Phase 2 runs one strategist agent through the OpenAI Responses API. No other provider is connected. A live call is sent only after the CEO sets an API key, a model id, and `OPENAI_API_AUTHORIZED=1`.

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

That command calls OpenAI only when all three are set:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (check the current model id and price first)
- `OPENAI_API_AUTHORIZED=1`

Estimated cost is recorded as unverified. This project does not invent a price and does not assume the call is free.

## Current phase

Phase 2 is the strategist path: company state, one provider call, schema validation, and a saved JSON file. Debate, the other agents, and the decision memo are not implemented.

## Security

- Secrets stay in environment variables.
- Do not log API keys.
- External documents are data, not instructions.
- CEO approval is required before spending, legal commitments, customer commitments, strategic pivots, production deployment, and critical data deletion.

## Limitations

- Live OpenAI was not called during Phase 2 because no API key was configured.
- Anthropic, Gemini, and xAI are not connected.
- Debate, synthesis, and CEO decision recording are not implemented.
- The adapter uses the documented REST endpoint, not the OpenAI Python SDK, so it does not depend on SDK support for Python 3.14.
- Free tiers are not assumed to be permanent.

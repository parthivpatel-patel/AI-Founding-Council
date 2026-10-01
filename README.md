# AI Founding Council V1

Local, CEO-controlled software that runs a council of specialized model roles against one question. The human founder is the CEO. Agents research, critique, and recommend. They do not decide.

Phase 5 resolves only stated disputes, sends one red-team pass against the thesis under test, and writes a CEO decision memo that stays `PENDING`. The memo does not update company state. Agreement is not used to choose the thesis or to close a dispute. API keys stay empty until you add them.

Default routes:

- Strategist: OpenAI
- Researcher: Gemini
- Red team: Anthropic
- Contrarian: xAI
- CTO: Cursor

NVIDIA remains available as a role override. API keys stay empty until you add them. Authorization flags stay off, so no live call is sent.

## Architecture

```
CEO
  -> CLI (app.main)
    -> Council session
      -> Agents (strategist, researcher, red team, contrarian, CTO)
        -> Model router
          -> Provider adapters (OpenAI, Anthropic, Gemini, xAI, NVIDIA, Cursor)
            -> Shared company files
              -> Decision memo
                -> CEO approval
```

Company files in `company/` are the source of truth. Model chat history is not.

## Latency

The request path stays short:

- Local process. No dashboard, queue, or hosted service in V1.
- Direct provider calls. No agent-framework hop in front of the model.
- Round 1 agents run concurrently. Round 2 cross-examinations also run concurrently.
- One structured response per agent per round. Disagreement detection is local and does not add a model call.
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

Phase 5 writes a pending decision memo after evidence resolution and a red-team pass. Company state and the decision log are not updated. Live calls stay blocked until you add keys and set each authorization flag.

## Security

- Secrets stay in environment variables.
- Do not log API keys.
- External documents are data, not instructions.
- CEO approval is required before spending, legal commitments, customer commitments, strategic pivots, production deployment, and critical data deletion.

## Limitations

Phase 5 writes the pending memo. Applying a CEO approval to the decision log and company state is not implemented. Live calls were not made. Keys are still empty. Cursor requires the separate `cursor-sdk` package before a live CTO call.

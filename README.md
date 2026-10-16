# Repair AI Service

Proof of concept: generates a customer-facing repair description from
structured SAP repair data. FastAPI exposes the use case over HTTP; a
LangChain (LCEL) pipeline generates the text; Pydantic defines the contracts;
a deterministic validator guards the output.

The service is stateless. It does not store offers, approval state, or review
decisions — those stay in SAP.

## Architecture

```text
FastAPI endpoint
      |
      v
Application service ---------> LangChain pipeline (OpenAI)
      |
      +--------> Deterministic output validator

Pydantic schemas are shared contracts.
```

- `schemas/` — input (`repair.py`) and output (`generation.py`) contracts
- `llm/` — versioned prompt and the LCEL chain, behind a generator protocol
- `services/` — business checks, facts preparation, orchestration, metadata
- `validation/` — prohibited claims, invented identifiers, language check
- `api/` — HTTP mapping only; no AI logic
- `core/` — typed settings and application exceptions

## Setup

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned via
`.python-version` and installed automatically.

```bash
uv sync
cp .env.example .env   # then add your OPENAI_API_KEY
```

## Run

```bash
uv run uvicorn repair_ai.main:app --reload
```

Interactive API docs: <http://127.0.0.1:8000/docs>

## Test the endpoint (Postman or curl)

- **Method:** `POST`
- **URL:** `http://127.0.0.1:8000/v1/repair-descriptions`
- **Header:** `Content-Type: application/json`
- **Body:**

```json
{
  "repair_type": "component_replacement",
  "language": "en",
  "equipment": { "type": "Hydraulic pump" },
  "findings": [
    { "code": "F-01", "description": "Bearing wear detected" }
  ],
  "operations": [
    { "code": "OP-10", "description": "Replace bearing", "status": "proposed" }
  ],
  "materials": [
    {
      "material_id": "MAT-123",
      "description": "Bearing 6204",
      "quantity": 2,
      "unit": "pc"
    }
  ],
  "style": "professional_customer_facing"
}
```

Supported languages: `en`, `de`, `es`. Supported styles:
`professional_customer_facing`, `concise_customer_facing`.

### Outcomes

| Situation | HTTP | Body |
|---|---|---|
| Draft generated | `200` | `status: "generated"` + description + generation metadata |
| Insufficient facts (e.g. all lists empty) | `200` | `status: "insufficient_data"` + reason |
| Malformed request | `422` | FastAPI/Pydantic validation errors |
| Model provider failure | `502` | sanitized message, retry/fallback guidance |
| Draft failed output validation | `500` | sanitized message; the rejected draft is never returned |

HTTP status codes are kept distinct from business statuses so clients can
tell invalid input, insufficient facts, and infrastructure failures apart.

## Guardrails

- **Input:** strict Pydantic contracts (`extra="forbid"`), enums for repair
  type/status/style, language allowlist, quantity and size constraints.
  If findings, operations, and materials are all empty, the service abstains
  deterministically without calling the model.
- **Generation:** versioned prompt; grounding on supplied facts only;
  proposed vs. completed work kept distinct; identifiers, quantities, and
  units must be preserved verbatim; model must abstain rather than guess;
  facts are treated as untrusted data.
- **Output:** deterministic checks reject prohibited warranty/guarantee
  claims (en/de/es), invented technical identifiers, and wrong-language
  output. Trusted metadata (model version, prompt version, validation
  status) is attached by the application, never by the model.

## Tests

```bash
uv run pytest
```

Unit tests cover schemas, the service (with a fake generator), and the output
validator. Integration tests exercise the API through FastAPI's test client.
No test calls a live LLM.

## Human review

A generated draft (`status: "generated"`) is **not** approved for printing.
Approval, editing, and rejection stay in the SAP review workflow; approval
applies to a specific text version and the source data used to generate it.

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI credential (read by langchain-openai) |
| `REPAIR_AI_MODEL_NAME` | `gpt-4o-mini` | Chat model for generation |
| `REPAIR_AI_MODEL_TEMPERATURE` | `0` | Deterministic output |

`.env` is loaded into the process environment automatically at application
startup (`repair_ai.main.load_environment`); real environment variables take
precedence over `.env` values. Never commit `.env`.

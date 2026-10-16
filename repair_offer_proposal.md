# Repair Offer AI Text-Generation Service — Proof of Concept Proposal

## 1. Objective

Build a small, modular Python application that generates a customer-facing repair description from structured SAP repair data. The proof of concept (PoC) should expose a FastAPI endpoint that can be tested independently with Postman.

The initial implementation should have three main layers:

1. **Pydantic contracts** — define the input and output data.
2. **LangChain pipeline** — generate a structured description from the repair facts.
3. **FastAPI API** — expose the generation use case over HTTP.

The architecture should be simple enough for a PoC but ready to grow into a controlled service with business validation, human review, evaluation, and integration with SAP ABAP.

The first version should not include a database, agents, RAG, autonomous SAP actions, price calculations, or complex orchestration. Its job is to turn supplied repair facts into clear customer-facing language.

## 2. Architectural principles

- Keep the SAP integration contract, text-generation logic, and evaluation framework independent.
- FastAPI handles HTTP; it should not contain the AI logic.
- The LangChain pipeline generates text; it should not know about HTTP or SAP transactions.
- Pydantic validates data shape and constraints, but does not prove that a generated claim is factually supported.
- The application service coordinates the use case and applies business rules.
- The model must not invent repairs, diagnoses, test results, warranties, guarantees, prices, or other unsupported facts.
- Human approval applies to a specific version of the text and the source data used to generate it.
- Keep the service stateless initially. Persist review and offer state in SAP if SAP is already the system of record.

## 3. High-level request flow

1. A client (Postman initially, SAP later) calls `POST /v1/repair-descriptions`.
2. FastAPI validates the request against the Pydantic request schema.
3. The application service applies deterministic business checks and prepares the factual input.
4. The LangChain pipeline passes a controlled prompt and the repair facts to the selected LLM.
5. The LLM returns structured output.
6. The application validates the result against output and business rules.
7. The API returns the description, status, and trusted generation metadata.
8. A reviewer approves, edits, or rejects the draft before it is used in a printed offer.

## 4. Suggested project structure

Use a `src`-based package structure to make imports and module boundaries explicit.

```text
repair-ai-service/
├── pyproject.toml
├── uv.lock
├── .env
├── .env.example
├── .gitignore
├── README.md
│
├── src/
│   └── repair_ai/
│       ├── __init__.py
│       ├── main.py
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py
│       │   └── endpoints/
│       │       ├── __init__.py
│       │       └── repair_descriptions.py
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── repair.py
│       │   └── generation.py
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   └── repair_description_service.py
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── chain.py
│       │   └── prompts.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   └── config.py
│       │
│       └── validation/
│           ├── __init__.py
│           └── output_validator.py
│
└── tests/
    ├── unit/
    │   ├── test_schemas.py
    │   └── test_service.py
    ├── integration/
    │   └── test_api.py
    └── evaluation/
        ├── cases/
        └── run_evaluation.py
```

This is a target structure, not a requirement to implement every file immediately. Keep the first iteration small, and introduce modules as the responsibilities become real.

### Module responsibilities

| Module | Responsibility |
|---|---|
| `main.py` | Creates the FastAPI app and registers the router |
| `api/router.py` | Groups endpoints under the `/v1` prefix |
| `api/endpoints/repair_descriptions.py` | Handles HTTP input/output and maps errors to HTTP responses |
| `schemas/repair.py` | Defines request and repair-data models |
| `schemas/generation.py` | Defines LLM output and API response models |
| `services/repair_description_service.py` | Coordinates validation, generation, and response mapping |
| `llm/chain.py` | Builds the LangChain pipeline |
| `llm/prompts.py` | Stores the versioned prompt template |
| `core/config.py` | Loads typed settings and environment configuration |
| `validation/output_validator.py` | Implements deterministic, repair-specific output checks |
| `tests/` | Contains unit, API integration, and model evaluation tests |

### Dependency direction

Keep dependencies flowing in one direction:

```text
FastAPI endpoint
      |
      v
Application service
      |
      +------> LangChain pipeline
      |
      +------> Output validator

Pydantic schemas are shared contracts.
```

Schemas should not import the API, service, or LangChain modules. The LangChain pipeline should not import FastAPI. The service should not know whether its caller is Postman, SAP, or a test. This reduces circular-import risk and makes components easier to test.

## 5. Initial Pydantic input schema

The following is an initial Pydantic v2 implementation. It intentionally keeps the request focused on repair facts and excludes prices and customer personal data from the first PoC.

Suggested file: `src/repair_ai/schemas/repair.py`

```python
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RepairType(StrEnum):
    COMPONENT_REPAIR = "component_repair"
    COMPONENT_REPLACEMENT = "component_replacement"
    INSPECTION = "inspection"
    MAINTENANCE = "maintenance"


class OperationStatus(StrEnum):
    PROPOSED = "proposed"
    COMPLETED = "completed"


class DescriptionStyle(StrEnum):
    PROFESSIONAL = "professional_customer_facing"
    CONCISE = "concise_customer_facing"


class RepairDataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Equipment(RepairDataModel):
    type: str = Field(min_length=1, max_length=150)


class RepairFinding(RepairDataModel):
    code: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=1000)


class RepairOperation(RepairDataModel):
    code: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    status: OperationStatus


class Material(RepairDataModel):
    material_id: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=20)


class RepairDescriptionRequest(RepairDataModel):
    request_id: UUID = Field(default_factory=uuid4)
    repair_type: RepairType
    language: str = Field(
        default="en",
        pattern=r"^[a-z]{2}(-[A-Z]{2})?$",
    )
    equipment: Equipment
    findings: list[RepairFinding] = Field(max_length=50)
    operations: list[RepairOperation] = Field(max_length=50)
    materials: list[Material] = Field(max_length=100)
    style: DescriptionStyle = DescriptionStyle.PROFESSIONAL
```

### Input schema design notes

- **Enums** constrain repair types, operation statuses, and styles to known values.
- `extra="forbid"` rejects unexpected fields instead of silently accepting them.
- Field constraints catch empty descriptions, oversized input, and invalid quantities before generation.
- The distinction between `PROPOSED` and `COMPLETED` is important: an offer may describe work that has not yet been performed.
- Optional codes allow the PoC to run before all SAP code mappings are finalized.
- Request IDs help correlate logs and troubleshoot a particular generation request.
- `float` is used for simplicity here. If quantities require exact decimal representation, consider `Decimal`.
- Decide whether empty findings, operations, or materials are valid for each repair type. Cross-field rules belong in the application/business validation layer.
- Decide whether equipment should be free text or a controlled identifier mapped to a technical description.
- `StrEnum` is available in Python 3.11+. Python 3.11 or newer is a straightforward choice for this project.

## 6. Initial Pydantic output schemas

Suggested file: `src/repair_ai/schemas/generation.py`

```python
from enum import StrEnum

from pydantic import Field, model_validator

from repair_ai.schemas.repair import RepairDataModel


class GenerationStatus(StrEnum):
    GENERATED = "generated"
    INSUFFICIENT_DATA = "insufficient_data"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class LLMGenerationOutput(RepairDataModel):
    """Structured output requested from the language model."""

    status: GenerationStatus
    description: str | None = Field(default=None, max_length=2000)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_status_consistency(self):
        if self.status == GenerationStatus.GENERATED:
            if not self.description or not self.description.strip():
                raise ValueError(
                    "A generated response must include a description."
                )
            if self.reason is not None:
                raise ValueError(
                    "A generated response must not include a reason."
                )

        if self.status == GenerationStatus.INSUFFICIENT_DATA:
            if self.description is not None:
                raise ValueError(
                    "An insufficient-data response must not include "
                    "a description."
                )
            if not self.reason or not self.reason.strip():
                raise ValueError(
                    "An insufficient-data response must include a reason."
                )

        return self


class GenerationMetadata(RepairDataModel):
    model_version: str
    prompt_version: str
    validation_status: ValidationStatus


class RepairDescriptionResponse(RepairDataModel):
    request_id: str
    status: GenerationStatus
    description: str | None = None
    reason: str | None = None
    generation: GenerationMetadata | None = None
```

### Output schema design notes

There are three distinct concepts:

1. **`LLMGenerationOutput`** is what the model is asked to produce.
2. **`GenerationMetadata`** is trusted application metadata.
3. **`RepairDescriptionResponse`** is the public API response.

The model should not be trusted to provide its own model version, prompt version, or validation result. The application should populate those fields from its actual configuration and validation process.

The status `generated` means a draft was generated; it does not mean the draft has been approved for printing. Approval is a separate business workflow.

The example uses a validator to enforce status consistency. A discriminated union could make the response contract stricter later, but this is a reasonable starting point for the PoC.

If common schema code grows, move `RepairDataModel` into a small `schemas/base.py` module. Avoid creating extra abstractions until they offer a concrete benefit.

## 7. LangChain pipeline

Use LangChain Expression Language (LCEL) for the initial pipeline. It composes a prompt and a model without introducing agent behavior.

Suggested files:

- `llm/prompts.py` — controlled, versioned prompt template.
- `llm/chain.py` — creates the prompt/model chain and exposes a generation function.

Conceptually, the chain is:

```python
prompt | model.with_structured_output(LLMGenerationOutput)
```

Verify structured-output support with the selected model integration.

### Prompt responsibilities

The system prompt should establish:

1. **Role:** Write clear, professional customer-facing descriptions for repair offers.
2. **Grounding:** Use only the supplied repair facts.
3. **Business semantics:** Distinguish proposed work from completed work.
4. **Claim restrictions:** Do not invent diagnoses, test results, warranties, guarantees, or additional work.
5. **Preservation:** Do not alter part numbers, quantities, or units.
6. **Insufficient data:** Return the appropriate status rather than filling gaps with assumptions.
7. **Output format:** Return the required structured schema.

Do not rely on the prompt for rules that can be enforced deterministically in Python. For example, quantity validation belongs in Pydantic, not just in prompt instructions.

### What should not belong in the chain

The chain should not read environment variables directly, create FastAPI response objects, handle HTTP status codes, persist approval state, or own the evaluation benchmark. Keep those concerns outside LangChain.

## 8. Application service

Suggested file: `services/repair_description_service.py`.

The service coordinates the use case:

1. Accept a validated `RepairDescriptionRequest`.
2. Apply deterministic business checks, including missing or contradictory data.
3. Prepare a factual representation of the input.
4. Invoke the LangChain pipeline.
5. Validate the output.
6. Map the result to `RepairDescriptionResponse`.
7. Attach trusted metadata such as model and prompt versions.

The service should depend on a generation interface rather than tightly coupling the whole application to one provider. That makes it possible to replace the model or use a fake implementation in tests.

Pydantic validates structure; it does not establish that every sentence is supported by the source. A separate output validator should check important identifiers, units, prohibited claims, and other repair-specific rules.

Start with simple, explainable checks. Add a second LLM-based critic only if evaluation shows that deterministic checks and the primary model are insufficient. An extra LLM call adds latency, cost, and another possible source of error.

## 9. FastAPI interface

Expose one endpoint initially:

- **Method:** `POST`
- **Path:** `/v1/repair-descriptions`
- **Request model:** `RepairDescriptionRequest`
- **Response model:** `RepairDescriptionResponse`

FastAPI should validate the incoming JSON, call the application service, and serialize the result. It should not contain generation logic.

FastAPI provides interactive API documentation at `/docs`, which is useful while developing and testing the endpoint.

### Error handling

- Malformed requests: FastAPI/Pydantic validation error, typically HTTP `422`.
- Valid request but insufficient repair facts: return the structured `insufficient_data` business outcome.
- Temporary model-provider failure: map to an appropriate server error and log the failure without exposing credentials or sensitive internals.
- Output validation failure: do not return the text as a usable generated draft; return a controlled failure outcome.

Keep HTTP status codes distinct from business statuses. This makes Postman testing easier and helps clients distinguish invalid input, insufficient facts, and infrastructure failures.

A health endpoint can be added after the generation endpoint works. Avoid calling the LLM on every health check.

## 10. Human review and approval

Human review is required before a description is printed. The initial review workflow can remain in SAP if the existing application provides a suitable place to show and approve the text; a separate AI user interface is not necessary for the PoC.

Recommended lifecycle:

1. Generate a draft.
2. Display it alongside the relevant source facts.
3. Allow a reviewer to approve, edit, or reject it.
4. Persist the approved text and its version association.
5. Print the approved snapshot.

Important rules:

- Approval applies to a specific text version and the source data used to generate it.
- If the source repair data changes, prior approval must not automatically authorize a new description.
- Editing invalidates approval until the edited version is approved.
- Printing must use the approved snapshot; do not regenerate text during printing.
- Record approval, edits, and rejection decisions in the appropriate system.

SAP should remain the system of record for repair offers and approval state if that is already where the business process is managed.

## 11. Guardrails

### Input validation

Before invoking the model, validate:

- Required fields and allowed values.
- Valid quantities and units.
- Supported repair types and languages.
- Proposed versus completed operation status.
- Contradictions between repair status and test results.
- Maximum list sizes and field lengths.

Missing data should remain missing; it must not be interpreted as a successful test or a negative finding.

### Generation rules

The model should write a clear description using only supplied facts. It must not invent root causes, additional work, successful testing, warranties, guarantees, or other unsupported outcomes. It must preserve technical identifiers and units.

Treat text fields as untrusted data, even when they originate in SAP. A free-text note must not be allowed to override the controlled system instructions.

### Output validation

| Check | Suggested implementation |
|---|---|
| Response structure | Pydantic validation |
| Identifiers | Compare extracted identifiers against the input |
| Quantities and units | Deterministic consistency checks |
| Text length | Maximum character or word count |
| Language | Validate against requested language |
| Prohibited claims | Rules with context-aware handling |
| Factual support | Semantic checks plus human review |

Keyword filters alone cannot reliably detect hallucinations. Use deterministic checks for objective constraints and semantic evaluation for meaning.

### Failure policy

If generation fails or validation rejects the output, do not return the rejected text as usable. Return an explicit outcome and let the caller apply a documented fallback policy. If AI text is optional, preserving the existing printing process may be appropriate, subject to business approval.

## 12. Configuration and dependencies

Use `pyproject.toml` as the dependency source of truth, `uv.lock` for reproducibility, and `core/config.py` for runtime settings.

Likely dependencies:

| Dependency | Purpose |
|---|---|
| `pydantic` | Data schemas and validation |
| `fastapi` | HTTP API |
| `uvicorn` | Local ASGI server |
| `langchain-core` | Prompt templates and LCEL |
| Provider-specific LangChain integration | Connects to the selected LLM |
| `pydantic-settings` | Typed environment-based configuration |
| `pytest` | Automated tests |
| `httpx` | FastAPI test client support |

Add the higher-level `langchain` package only if the project needs functionality beyond `langchain-core` and the provider integration.

The actual model provider remains a decision. Since an enterprise-approved SAP AI platform is available, investigate SAP AI Core / Generative AI Hub and verify your organization's entitlements, supported models, region, networking, identity integration, and data-processing requirements. Keep business validation in your application even if the platform offers generic content filters or orchestration.

Keep credentials in environment variables or an approved secrets manager. Do not commit `.env`; commit `.env.example` with placeholder variable names only.

## 13. Testing strategy

Use three levels of testing.

### Unit tests

Test schema constraints, status consistency, missing fields, invalid quantities, business rules, and output validation. These tests should not call a live LLM.

### API integration tests

Use FastAPI's test client and replace the real generation pipeline with a deterministic fake. Test response models, HTTP status codes, malformed requests, and error handling.

### Real-model tests and evaluation

Run a dedicated evaluation suite against the chosen model using representative repair cases. Check factual correctness, completeness, language, technical preservation, and behavior on incomplete or contradictory inputs.

Do not call a live model in every ordinary automated test run. Use deterministic mocks in normal CI and run the model evaluation suite when the model, prompt, schema, or generation configuration changes.

## 14. Evaluation framework

Evaluation should be a separate development and release pipeline, not a costly step in every production request.

### Build a frozen benchmark

Start with approximately 100–300 representative, anonymized repair cases if feasible. This is a practical starting target, not a statistical guarantee.

Each case should include:

- The exact normalized input sent to the model.
- An expert-approved reference description where available.
- Required facts and permitted claims.
- Prohibited claims or known failure modes.
- Expected behavior, including whether to generate or abstain.
- Repair category and language.

Maintain three datasets:

- **Development set:** used to refine prompts and rules.
- **Frozen regression set:** used for repeatable comparisons and not for routine tuning.
- **Challenge set:** contains difficult cases such as missing fields, contradictory data, unusual combinations, and technical language edge cases.

A single reference paragraph cannot capture every valid description. Store required facts and expected behavior as well as reference wording.

### Metrics

| Metric | Definition |
|---|---|
| Critical unsupported-claim rate | Cases containing invented or materially misleading claims |
| Required-fact coverage | Required facts correctly reflected in the output |
| Contradiction rate | Outputs that contradict source data |
| Abstention accuracy | Whether the service correctly refuses when data is insufficient |
| Technical preservation | Correct part numbers, quantities, units, and terminology |
| Human acceptance rate | Drafts approved without substantive edits |
| Edit rate | Frequency of reviewer corrections |
| Operational reliability | Availability, latency, failures, and fallback frequency |

Treat factual errors, contradictions, and incorrect handling of proposed versus completed work as release-blocking issues.

### Release gates

Before promoting a new version:

- No critical factual errors in the frozen release benchmark.
- All deterministic schema and business-rule checks pass.
- Missing-data and contradictory-data cases behave as specified.
- No unresolved high-severity security or privacy findings.
- Business-approved targets for fact coverage, reviewer acceptance, latency, and cost are met for each important language and repair category.
- Any regression against the approved version has been reviewed.

Zero observed errors in a benchmark does not prove the true error rate is zero. Combine benchmark testing with human review, challenge cases, and production monitoring.

### Feedback loop

Capture review outcomes such as approved without changes, stylistic edit, factual correction, insufficient input, or rejection. Use them to discover recurring failure modes and improve the development or challenge datasets.

Do not automatically train on reviewer edits. First determine whether an edit reveals a mapping issue, missing business rule, prompt issue, or model limitation, then make a controlled change and rerun evaluation.

## 15. Suggested implementation sequence

1. **Finalize the contracts and business rules.** Decide supported repair types, languages, empty-list behavior, and insufficient-data behavior.
2. **Set up the package and dependencies.** Create the `src` structure and configure `uv`.
3. **Build the LangChain pipeline independently.** Test structured generation with a small sample of repair records.
4. **Implement the application service and output validation.**
5. **Add the FastAPI endpoint.** Test it through Postman and `/docs`.
6. **Create the initial evaluation set.** Capture expected behavior and representative edge cases.
7. **Integrate with non-production SAP.** Initially run in shadow mode without using AI text in real printed offers.
8. **Roll out under human review.** Keep a feature flag, documented fallback, and monitoring.

## 16. Decisions to finalize before implementation

The most important open decisions are:

1. Which repair types are in scope for the first PoC?
2. Can findings, operations, or materials be empty, and under what conditions?
3. Which languages are required initially?
4. Should language be an ISO-style code such as `en` or `es`, or does SAP require a different language-code mapping?
5. Are quantities always numeric and exact, or should the schema use `Decimal`?
6. Which enterprise model platform and model integration will be used?
7. Where will the approved text and reviewer decision be stored when SAP integration is introduced?
8. What should happen if data is insufficient or the model is unavailable?

## Final recommendation

Keep three things independent: **the SAP integration contract, the text-generation logic, and the evaluation framework**. Begin with one endpoint, a strict request schema, a controlled LangChain prompt, structured model output, and a small deterministic validator. Add complexity only when evaluation shows a concrete need.

The first implementation milestone should be finalizing the Pydantic contracts—especially repair type, optional and empty fields, language representation, and insufficient-data behavior—because every other component depends on those decisions.

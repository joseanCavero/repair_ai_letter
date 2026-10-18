# Render Deployment Plan — Repair AI Service

## 1. Goal and scope

Deploy the existing Repair AI Service from GitHub to Render so it can be called over HTTPS from Postman. Keep the current architecture: FastAPI exposes the endpoint, Pydantic defines the request/response contracts, LangChain generates the draft, and deterministic validation checks the output.

This is a **personal proof of concept**, not an approved company service. Use synthetic or anonymized repair examples only. Do not send confidential company, customer, or SAP data to this personal deployment unless explicitly authorized.

### Target architecture

```text
VS Code / local development
        |
        | git push
        v
GitHub repository
        |
        | build and deploy
        v
Render web service (HTTPS)
        |
        | authenticated POST /v1/repair-descriptions
        v
FastAPI -> application service -> LangChain/OpenAI -> output validator
        |
        v
Draft response to Postman (not approved for printing)
```

Render hosts the API. OpenAI remains the model provider for the first deployment. The service remains stateless; no database or approval workflow is added.

## 2. Assumptions to verify

The supplied README describes Python 3.12, `uv`, `repair_ai.main:app`, `POST /v1/repair-descriptions`, and these settings:

- `OPENAI_API_KEY`
- `REPAIR_AI_MODEL_NAME` (default `gpt-4o-mini`)
- `REPAIR_AI_MODEL_TEMPERATURE` (default `0`)

Before configuring Render, confirm that the repository actually contains `pyproject.toml`, `uv.lock`, `.python-version`, and the `repair_ai` package in a layout compatible with the README's local startup command. The deployment commands below assume the application is importable from the repository root. Adjust them if the actual package configuration differs.

## 3. Before deploying: prepare the repository

### 3.1 Check the tracked files

At minimum, check that the repository contains:

- `pyproject.toml`
- `uv.lock`
- `.python-version` set to Python 3.12
- `src/repair_ai/` or the package layout used by the project
- Tests and test configuration
- `.gitignore`
- `.env.example` with variable names and placeholder values only

Commit `uv.lock` so the deployment uses reproducible dependency versions. Ensure `.env` is ignored by Git and that no API key or other secret is present in tracked files or commit history.

Example local checks:

```bash
uv sync
uv run pytest
uv run uvicorn repair_ai.main:app --reload
```

Open `http://127.0.0.1:8000/docs` and test the endpoint locally before deploying.

### 3.2 Add health endpoints

The README does not establish that health endpoints already exist. Add them before deployment, ideally with distinct purposes:

- `GET /health/live`: confirms the process is running.
- `GET /health/ready`: confirms the app has initialized and is ready to accept requests.

These checks should not call the LLM. A health endpoint should not expose secrets, configuration values, stack traces, or customer data. Configure Render to use `/health/ready` as its health-check path once implemented.

### 3.3 Add API authentication before public exposure

The README does not document endpoint authentication. Unless it exists elsewhere in the code, assume the endpoint is not protected. Do not expose it publicly without access control.

For a single-user PoC, a small FastAPI dependency requiring a strong random API key in an `X-API-Key` header is a reasonable first step:

1. Generate a high-entropy random key.
2. Store the expected key in a Render environment secret, for example `REPAIR_AI_API_KEY`.
3. Require the header on the generation endpoint.
4. Reject missing or incorrect keys with `401` or `403`.
5. Compare secret values safely and never log the key.
6. Keep authentication tests in the test suite.

This is a lightweight PoC measure, not a substitute for enterprise identity and authorization. If the endpoint later serves multiple users or company systems, adopt an appropriate OAuth/OIDC-based design.

### 3.4 Set safe operational limits

Before treating the service as internet-accessible, check that it has:

- A bounded request-body size.
- Explicit model-call and overall request timeouts.
- Bounded retries (avoid retry storms and repeated billable calls).
- Sensible output-token/generation limits where supported by the model integration.
- Sanitized error responses.
- No API keys, prompts containing sensitive data, or full repair payloads in ordinary logs.

The existing README describes `502` for provider failures and `500` for rejected drafts. Preserve sanitized responses and ensure internal logs are useful without leaking secrets or rejected model output.

## 4. Create the Render service

### 4.1 Connect GitHub

1. Sign in to Render.
2. Choose **New** and create a **Web Service**.
3. Connect GitHub if it is not already connected.
4. Select the Repair AI Service repository.
5. Choose the branch to deploy (for example, `main` after changes have passed review and tests).
6. Give the service a clear name, such as `repair-ai-service`.

Use the current Render dashboard labels if they differ slightly from these instructions.

### 4.2 Configure build and runtime

Assuming `uv.lock` is committed and the app is importable from the repository root, start with:

| Setting | Suggested value |
|---|---|
| Runtime | Python 3 |
| Build command | `uv sync --frozen --no-dev` |
| Start command | `uv run --no-sync uvicorn repair_ai.main:app --host 0.0.0.0 --port $PORT` |
| Health-check path | `/health/ready` (after implementing it) |
| Auto-deploy | Enable after the first successful manual verification; deploy from the selected branch |

Notes:

- Render provides the `$PORT` environment variable; bind Uvicorn to `0.0.0.0` and that port.
- Do not use `--reload` in production.
- `uv sync --frozen` expects a lockfile consistent with `pyproject.toml`.
- `--no-dev` assumes production runtime dependencies are declared separately from development dependencies.
- The start command assumes the import path shown in the README works from the service's working directory. Verify it from the actual repository before relying on it.
- If Render's selected runtime image does not have `uv` available by default, configure the build environment to install a pinned `uv` version or use a supported build approach documented by Render. Avoid relying on an unpinned, implicit tool installation.

For the first deployment, it is reasonable to leave auto-deploy disabled until the service has passed a manual smoke test. Then enable automatic deployments for the chosen branch if desired.

## 5. Configure environment variables and secrets

In the Render service's environment settings, add the values needed at runtime. Do not put secrets into the repository, build command, or source code.

| Variable | Value / handling |
|---|---|
| `OPENAI_API_KEY` | Enter your personal OpenAI API key as a secret in Render. Never commit it. |
| `REPAIR_AI_MODEL_NAME` | `gpt-4o-mini`, or the model you have selected and verified. |
| `REPAIR_AI_MODEL_TEMPERATURE` | `0`, as described in the README. |
| `REPAIR_AI_API_KEY` | Add this if you implement the API-key authentication described above. |

Also configure any other variables actually required by `core/config.py`. The list above is based on the supplied README, not a complete source-code audit.

Keep `.env.example` safe for developers: include names and placeholder values only. The application may load `.env` locally, but production credentials should come from Render's environment/secret settings. Never print secret values during startup or in exception messages.

## 6. Deploy and verify

After creating the service, wait for the build and deployment to finish. Inspect build/runtime logs for import errors, missing dependencies, configuration failures, or failed health checks. Logs should not contain credentials.

### 6.1 Smoke tests

Use the actual HTTPS service URL shown by Render. Do not assume or invent a URL before the service has been created.

1. Call `GET /health/live` and confirm a successful response.
2. Call `GET /health/ready` and confirm a successful response.
3. Open `/docs` if interactive documentation is enabled and appropriate for the PoC.
4. Send an authenticated request to `POST /v1/repair-descriptions` using a synthetic example based on the README.
5. Confirm the response is a draft and that `status: "generated"` is not interpreted as approval to print.

Example request body:

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

Send these headers in Postman:

```text
Content-Type: application/json
X-API-Key: <your configured API key>
```

If you choose a different authentication mechanism, replace the header accordingly. Keep the real key in Postman's secret/current-value handling rather than saving it in a shared collection or exported environment file.

### 6.2 Test expected outcomes

| Test | Expected result |
|---|---|
| Valid synthetic request | `200`, generated draft and trusted generation metadata |
| All relevant fact lists empty | `200`, `insufficient_data`, if this matches the implemented service behavior |
| Malformed request | `422` from request validation |
| Missing/invalid API key | `401` or `403`, depending on implementation |
| Provider failure | Sanitized `502`, per the README |
| Draft rejected by output validation | Sanitized `500`, and rejected draft is not returned |
| Health endpoint | Successful response without an LLM call |

These are target expectations from the README and proposed authentication/health additions. Confirm them against the implementation and tests rather than assuming every behavior already exists.

## 7. Continuous integration and deployment

Before enabling automatic deployment from GitHub, add a CI workflow that runs on pull requests and pushes to the deployment branch. At minimum:

1. Install Python 3.12 and a pinned `uv` version.
2. Install dependencies using the committed lockfile.
3. Run `uv run pytest`.
4. Optionally add formatting/linting and type checks once configured.
5. Consider dependency and secret scanning.

The current test strategy is a good foundation because unit and integration tests use a fake generator and do not require a live LLM. Do not put the OpenAI API key into CI unless a separate, intentional live-model evaluation job requires it. Keep live-model evaluation separate from routine tests to control cost and avoid flaky CI.

For a personal PoC, GitHub Actions plus Render's Git integration is sufficient. You do not need a complex multi-environment release system initially, but you should know which commit is deployed and how to roll back to a previous working commit/deployment.

## 8. Monitoring, cost, and data handling

- Review Render service logs after deployment and when requests fail.
- Track request volume, latency, HTTP status codes, provider errors, and output-validation failures.
- Where possible, attach a request/correlation ID to logs and responses.
- Do not log the API key, full prompts, or repair payloads by default.
- Monitor OpenAI API usage and configure any available budget/usage alerts in the provider account.
- Set request and generation limits to reduce abuse and unexpected model spend.
- Use only synthetic or anonymized data in the personal service unless the data owner has authorized the use.
- Remember that generated content is a draft. Human review remains necessary before it is used in a customer offer or printed.

A stateless API does not automatically mean no data is retained anywhere: hosting logs and the model provider may process or retain data according to their respective settings and policies. Review those terms before sending any sensitive data.

## 9. Troubleshooting checklist

### Build fails

- Check that `pyproject.toml` and `uv.lock` are committed and consistent.
- Check that the required package is included in production dependencies.
- Confirm the configured Python version is compatible with the dependency set.
- Check whether the build environment has the expected `uv` version.

### App fails to start

- Verify the import path `repair_ai.main:app` and working directory.
- Check that the app binds to `0.0.0.0` and `$PORT`.
- Check for missing required environment variables and startup-time exceptions.
- Review logs without exposing secret values.

### Health check fails

- Confirm the configured path exists and returns a successful status.
- Ensure the health check does not call the LLM or depend on an external provider being available.
- Check that the app finishes startup successfully.

### API returns provider errors

- Verify the OpenAI key is valid and configured as a runtime secret.
- Verify model access and account billing/usage limits.
- Check timeouts and sanitized logs.
- Avoid adding unbounded retries; each retry may create additional cost.

### Postman cannot call the endpoint

- Copy the actual service URL from Render.
- Use HTTPS and the correct route.
- Include the configured authentication header.
- Check whether the service is healthy and whether the request schema matches the Pydantic contract.

## 10. Release checklist

Use this checklist before considering the PoC deployed:

- [ ] `uv.lock` is committed and consistent with `pyproject.toml`.
- [ ] `.env` and secrets are excluded from Git.
- [ ] `uv run pytest` passes locally and in CI.
- [ ] Health endpoints exist and do not call the LLM.
- [ ] Authentication is implemented and tested before public exposure.
- [ ] Request size and model-call timeouts are bounded.
- [ ] Render environment variables are configured securely.
- [ ] Build and start commands match the actual repository layout.
- [ ] Deployment succeeds and health checks pass.
- [ ] Authenticated Postman smoke test succeeds using synthetic data.
- [ ] Invalid input, insufficient data, provider errors, and output-validation failures are tested.
- [ ] Logs do not expose secrets or sensitive repair data.
- [ ] Model usage/cost is monitored.
- [ ] Rollback to a known working deployment/commit is understood.

## 11. Official references

- Render: [Deploy a FastAPI app](https://render.com/docs/deploy-fastapi)
- Render: [Environment variables and secrets](https://render.com/docs/configure-environment-variables)
- Render: [Health checks](https://render.com/docs/health-checks)
- Astral `uv`: [Using uv in Docker and deployment environments](https://docs.astral.sh/uv/guides/integration/docker/)

## 12. Recommended next step

Before implementing this plan, inspect the repository's actual `pyproject.toml`, `.python-version`, `.gitignore`, `core/config.py`, application entry point, and API router. Then implement the missing health/authentication safeguards, validate the build and start commands locally, and deploy to Render. This plan is based on the supplied README; it does not claim that those safeguards or endpoints already exist.

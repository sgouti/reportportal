# Analyzer Insights Docker Deployment Guide

## Purpose

This document explains:

- what was added for the Analyzer Insights rollout
- which source directories and Docker images must contain the changes
- how the auto-analyzer image handles ML model assets
- how to deploy the feature set in Docker in a way that is testable and production-oriented

The examples assume the top-level compose file at the repository root and a compose project name of `trading`. Replace the project name if your environment uses a different one.

## Feature Set Included In This Rollout

### UI features

The `service-ui` changes add a new Analyzer Insights surface and richer ML-assisted triage UI:

- Analyzer Insights page in the project area
- Overview tab with analyzer coverage, comparison summary, triage aging, and flaky candidate KPIs
- Quarantine tab for flaky candidates
- Root-cause clusters panel with expandable clustered test items and triage actions
- Flakiness details modal for a selected test item
- Ranked ML suggestions in the Make Decision modal
- Confidence score indicator for ML suggestions
- Hybrid search indicator showing suggestion source and ranking method

### API features

The `service-api` changes are required for the new UI to work end-to-end:

- `GET /api/v1/{projectKey}/analyzer/insights`
- `GET /api/v1/{projectKey}/analyzer/insights/item/{itemId}/flakiness`

If the UI is upgraded without the matching `service-api` image, the page will render but the insights calls can return `404`.

### Analyzer runtime features

The `service-auto-analyzer` codebase contains the ML runtime behavior used by the new insights data and suggestion flow:

- semantic embeddings with `BAAI/bge-m3`
- hybrid lexical plus dense retrieval
- ONNX reranking with `BAAI/bge-reranker-base`
- LightGBM-based suggestion and auto-analysis training
- Optuna tuning when validation quality drops below threshold
- flaky score and quarantine detection persisted into OpenSearch documents
- backfill script for old indexed data

## Source Directories That Must Include The Changes

Use this map when deciding what to pull, rebuild, or promote.

| Area | Path in this workspace | Why it matters |
| --- | --- | --- |
| Top-level deployment | `docker-compose.yml` | Controls which image tags are deployed through compose |
| UI | `service-ui` | Contains the new Analyzer Insights page and ML suggestion UI |
| API | `service-api` | Exposes the new insights and flakiness endpoints |
| Analyzer | `service-auto-analyzer` | Supplies clustering, semantic ranking, reranking, flakiness, and backfill behavior |

### Important note about `service-ui`

In this workspace, `service-ui` is a nested git repository/submodule. If you deploy from git instead of a container registry, update both:

- the top-level `reportportal` repo
- the nested `service-ui` repo reference

If you only update the parent repo without updating the nested `service-ui` content, the built UI image can lag behind the intended code.

## Docker Images You Need To Pull Or Build

These are the compose-controlled images relevant to this feature set.

| Compose variable | Default image in compose | Custom image needed for this rollout | Required |
| --- | --- | --- | --- |
| `UI_IMAGE` | `reportportal/service-ui:5.15.2` | Yes, if you want the new Analyzer Insights UI | Yes |
| `API_IMAGE` | `reportportal/service-api:5.15.1` | Yes, if you want the new insights endpoints | Yes |
| `ANALYZER_IMAGE` | `reportportal/service-auto-analyzer:5.15.1` | Recommended if you want the modernized semantic and flaky runtime behavior | Recommended |
| `UAT_IMAGE` | `reportportal/service-authorization:5.15.0` | No, unless you changed auth code | No |
| `JOBS_IMAGE` | `reportportal/service-jobs:5.15.0` | No | No |
| `INDEX_IMAGE` | `reportportal/service-index:5.15.0` | No | No |
| `MIGRATIONS_IMAGE` | `reportportal/migrations:5.15.1` | No for this specific feature set | No |

### Minimum image set

For the Analyzer Insights page to work correctly in Docker, the minimum aligned custom image set is:

- custom `service-ui`
- custom `service-api`

### Recommended image set

For a production-like rollout that includes the newer ML runtime behavior, use:

- custom `service-ui`
- custom `service-api`
- custom `service-auto-analyzer`

## Recommended Release Strategy

### Option A: Promote prebuilt images from CI

This is the production path.

Build and push immutable tags from CI, then deploy them with compose variables:

```powershell
$env:UI_IMAGE = 'your-registry/reportportal/service-ui:analyzer-insights-2026-03-14'
$env:API_IMAGE = 'your-registry/reportportal/service-api:analyzer-insights-2026-03-14'
$env:ANALYZER_IMAGE = 'your-registry/reportportal/service-auto-analyzer:analyzer-insights-2026-03-14'

docker compose -p trading pull ui api analyzer
docker compose -p trading up -d --no-build ui api analyzer
```

### Option B: Build locally, then deploy with compose overrides

This is suitable for test environments.

```powershell
Set-Location 'c:\Users\siddh\reportportal\reportportal'

docker build -t your-registry/reportportal/service-ui:analyzer-insights .\service-ui
docker build -t your-registry/reportportal/service-api:analyzer-insights .\service-api
docker build -t your-registry/reportportal/service-auto-analyzer:analyzer-insights .\service-auto-analyzer

$env:UI_IMAGE = 'your-registry/reportportal/service-ui:analyzer-insights'
$env:API_IMAGE = 'your-registry/reportportal/service-api:analyzer-insights'
$env:ANALYZER_IMAGE = 'your-registry/reportportal/service-auto-analyzer:analyzer-insights'

docker compose -p trading up -d --no-build ui api analyzer
```

### Windows build note for `service-api`

For production delivery, prefer CI or a Linux builder for `service-api`. In this workspace, local Windows-mounted Gradle and Docker builds were unreliable, while the source code itself was present. For stable releases, treat the API image build as a CI responsibility.

## How The Auto-Analyzer Pulls ML Models

This is the key behavior to understand.

### Short version

The analyzer does **not** automatically download Hugging Face model assets when the container starts.

Instead, model download is designed as a **build-time** step when you explicitly enable model baking.

### Build-time model baking

The `service-auto-analyzer` Dockerfile has a `model-download` stage. If you pass `BAKE_MODELS=true`, it runs `app/ml/bake_models.py` during the image build.

Example:

```powershell
docker build \
  --build-arg BAKE_MODELS=true \
  --build-arg HF_TOKEN=$env:HF_TOKEN \
  -t your-registry/reportportal/service-auto-analyzer:analyzer-insights-offline \
  .\service-auto-analyzer
```

What `bake_models.py` does:

- calls `huggingface_hub.snapshot_download(...)`
- downloads only the allowed runtime artifacts, mainly ONNX files and tokenizer metadata
- writes them into the configured local model directories

Default baked locations:

- `res/model/runtime/bge-m3`
- `res/model/runtime/bge-reranker-base`

Default remote model ids:

- `BAAI/bge-m3`
- `BAAI/bge-reranker-base`

### Runtime model loading

At runtime, the semantic layer reads these settings from environment variables:

- `AA_MODEL_CACHE_DIR`
- `AA_BGE_M3_MODEL_ID`
- `AA_BGE_RERANKER_MODEL_ID`
- `AA_BGE_M3_MODEL_PATH`
- `AA_BGE_RERANKER_MODEL_PATH`
- `AA_BGE_M3_MODEL_FILE`
- `AA_BGE_RERANKER_MODEL_FILE`

The FastEmbed loaders are initialized with `local_files_only=true`. That means runtime expects the model files to already exist locally inside the container filesystem or in a mounted volume.

### What happens if model files are missing

If the semantic embedder or reranker cannot be initialized, the service falls back to hashing-based implementations instead of crashing.

That means:

- the analyzer container can still start
- suggestions and ranking still work in a degraded mode
- semantic quality is lower than with baked ONNX assets

### Production recommendation for models

Use one of these two approaches:

1. Bake the model artifacts into the analyzer image.
2. Mount a read-only model directory into the analyzer container and point the `AA_BGE_*_MODEL_PATH` variables at it.

For production, baking or mounting is preferred over depending on any implicit remote fetch behavior.

## How The Analyzer Integrates With ReportPortal

The analyzer service integrates with the rest of the stack through these dependencies:

- RabbitMQ via `AMQP_URL`, `AMQP_EXCHANGE_NAME`, and `AMQP_VIRTUAL_HOST`
- OpenSearch via `ES_HOSTS`
- shared storage via `/data/storage/analyzer`

The analyzer starts two AMQP processing flows:

- a main handler for indexing, searching, suggesting, clustering, and cleanup requests
- a dedicated training handler for `train_models`

The compose service already wires the analyzer to:

- `rabbitmq`
- `opensearch`
- the shared `storage` volume

## Deployment Instructions

### 1. Build or publish the aligned images

At minimum, publish aligned UI and API images from the same release candidate.

Recommended set:

- `service-ui`
- `service-api`
- `service-auto-analyzer`

### 2. Inject image tags into compose

```powershell
Set-Location 'c:\Users\siddh\reportportal\reportportal'

$env:UI_IMAGE = 'your-registry/reportportal/service-ui:analyzer-insights-rc1'
$env:API_IMAGE = 'your-registry/reportportal/service-api:analyzer-insights-rc1'
$env:ANALYZER_IMAGE = 'your-registry/reportportal/service-auto-analyzer:analyzer-insights-rc1'
```

### 3. Deploy the changed services

```powershell
docker compose -p trading up -d --no-build ui api analyzer
```

If you also changed auth, jobs, or index, add those services explicitly. Otherwise leave them on the compose defaults.

### 4. Wait for health checks

Expected internal health endpoints:

- UI: `http://localhost:8080/health` inside the container
- API: `http://localhost:8585/health` inside the container
- UAT: `http://localhost:9999/health` inside the container
- Analyzer: `http://localhost:5001/` inside the container

### 5. Backfill old analyzer data if needed

If you are enabling new semantic vectors or flaky metadata for already indexed historical data, run a backfill job against the analyzer image.

Example:

```bash
AA_BACKFILL_PROJECTS=1,2,3 python app/ml/backfill_runtime_fields.py
```

Use this only when you need historical OpenSearch documents upgraded with semantic and flaky fields.

## Production-Ready Checklist

Use this checklist before calling the deployment ready.

- UI image and API image are built from the same release tag
- Analyzer image is aligned with the desired ML runtime behavior
- Mutable tags like `latest` are not used
- Images are pulled from a registry or promoted from CI, not rebuilt manually on production hosts
- Analyzer model assets are either baked into the image or mounted explicitly
- OpenSearch, RabbitMQ, PostgreSQL, and gateway are healthy before app smoke tests run
- The compose project name used for deployment matches the active environment
- Historical data backfill has been planned if semantic or flaky fields are required for old launches

## Smoke Test Plan

### API smoke test

Get an auth token and verify the new endpoint responds:

```powershell
$token = (Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/uat/sso/oauth/token' `
  -Headers @{ Authorization = 'Basic dWk6dWltYW4=' } `
  -ContentType 'application/x-www-form-urlencoded' `
  -Body 'grant_type=password&username=superadmin&password=erebus').access_token

Invoke-RestMethod -Method Get -Uri 'http://localhost:8080/api/v1/sid/analyzer/insights?historyDepth=10' `
  -Headers @{ Authorization = "Bearer $token" }
```

Expected result:

- HTTP `200` from the insights endpoint
- not `404`

### UI smoke test

Open:

- `http://localhost:8080/ui/`

Then navigate to:

- project sidebar entry for Analyzer Insights

Expected result:

- page loads without gateway `504`
- overview cards render
- quarantine and cluster sections render when data exists

### Analyzer smoke test

Confirm the analyzer container is healthy and, if semantic mode is expected, inspect logs for model initialization instead of hashing fallback warnings.

## Common Failure Modes

### UI updated, API not updated

Symptom:

- Analyzer Insights page loads, but calls to `/api/v1/{project}/analyzer/insights` return `404`

Fix:

- deploy the matching `service-api` image

### Analyzer image deployed without baked models

Symptom:

- analyzer works, but semantic quality is lower and logs show fallback to hashing embedder or reranker

Fix:

- rebuild analyzer with `BAKE_MODELS=true`, or mount local model assets

### Wrong compose project name

Symptom:

- containers start, but gateway routing returns `504` or does not reach the intended stack

Fix:

- deploy into the correct compose project, for example `docker compose -p trading ...`

## Recommended Release Boundary

For this specific feature family, the safest release boundary is:

- `service-ui`
- `service-api`
- `service-auto-analyzer`
- top-level compose image overrides

That combination produces a testable stack where:

- the UI can request the new data
- the API can serve the new endpoints
- the analyzer can provide the richer ML signals used by the experience
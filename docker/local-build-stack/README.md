# Local Build Stack

This folder provides a self-contained Docker Compose entrypoint for building the ReportPortal service images from the current workspace and running the full stack locally.

The compose file builds these local services from source in this repository:

- `migrations`
- `service-index`
- `service-ui`
- `service-api`
- `service-authorization`
- `service-jobs`
- `service-auto-analyzer`

The service Dockerfiles remain in their original service directories. This folder adds the runtime compose, environment template, and helper scripts so the stack can be launched from one place.

## Files

- `compose.yaml`: local full-stack deployment file
- `.env.example`: image tags and runtime defaults
- `up.ps1`: builds and starts the stack
- `down.ps1`: stops the stack

## Usage

1. Copy `.env.example` to `.env` if you want to override defaults.
2. Optionally set `HF_TOKEN` in `.env` if you want authenticated model downloads during analyzer image build.
3. Run `./up.ps1` from this folder.
4. Open `http://localhost:8080` after the health checks pass.

Default local credentials in this folder:

- username: `admin@reportportal.internal`
- password: `erebus`

## Notes

- The stack uses the current checked-out source from the repository as Docker build context.
- Analyzer image builds default to `BAKE_MODELS=true`. Set it to `false` in `.env` if you want a faster build with runtime fallback behavior.
- If another ReportPortal stack is already bound to ports `8080`, `8081`, or `443`, stop it first or change the exposed ports in `compose.yaml`.
# Deployment

Production runs from [`docker-compose.prod.yml`](../docker-compose.prod.yml). It is a self-contained stack — no bind mounts, no hot reload, no dev tooling. All secrets come from environment variables injected at deploy time; nothing sensitive lives in the repository.

## What the stack runs

| Service | Role |
|---|---|
| `postgres` | Primary data store |
| `redis` | Celery broker and result backend |
| `migrate` | One-shot Alembic migration runner; exits before `api` starts |
| `api` | FastAPI application (uvicorn, 4 workers) |
| `worker` | Celery worker — runs fetch and scoring tasks |
| `beat` | Celery Beat — fires scheduled fetches |
| `web` | nginx serving the built React SPA, proxying `/api/` to `api:8000` |

## Prerequisites

- Docker and Docker Compose v2
- A reverse proxy in front of the stack (nginx, Traefik, Caddy — anything that terminates TLS)
- An OIDC provider (see [`docs/auth.md`](auth.md))
- An LLM API key — Anthropic or OpenAI (see [LLM section](#llm) below)

## Environment variables

All variables must be injected at deploy time. None of them belong in the repository.

### Required

| Variable | Description |
|---|---|
| `POSTGRES_USER` | Database username |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name |
| `SESSION_SECRET` | JWT signing secret — `openssl rand -hex 32` |
| `OIDC_ISSUER` | OIDC provider issuer URL |
| `OIDC_CLIENT_ID` | OIDC client ID |
| `OIDC_CLIENT_SECRET` | OIDC client secret |
| `OIDC_REDIRECT_URI` | Must match the registered redirect URI exactly, e.g. `https://jobs.yourdomain.com/api/auth/callback` |

### Reverse proxy

| Variable | Description | Default |
|---|---|---|
| `APP_DOMAIN` | Public hostname (used in Traefik labels) | — required if using Traefik |
| `CERT_RESOLVER` | Traefik certificatesResolvers entry name | `letsencrypt` |
| `TRAEFIK_NETWORK` | External Docker network Traefik listens on | `traefik` |

### Optional

| Variable | Description | Default |
|---|---|---|
| `LOG_LEVEL` | Log verbosity | `INFO` |
| `LLM_PROVIDER` | `anthropic` or `openai` | `anthropic` |
| `LLM_MODEL` | Model ID for the selected provider | `claude-sonnet-4-6` |
| `ANTHROPIC_API_KEY` | Required when `LLM_PROVIDER=anthropic` | — |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai` | — |
| `OIDC_ALLOWED_EMAILS` | Comma-separated allowlist; blank = any authenticated user | — |
| `ADZUNA_APP_ID` | Adzuna API app ID | — |
| `ADZUNA_APP_KEY` | Adzuna API app key | — |
| `REED_API_KEY` | Reed.co.uk API key | — |

---

## LLM

Job Finder uses an LLM for three tasks: CV parsing on upload, scoring each job against the CV, and parsing freeform HN "Who is hiring?" comments. You need an API key for at least one provider.

- **Anthropic** — [console.anthropic.com](https://console.anthropic.com). Set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.
- **OpenAI** — [platform.openai.com](https://platform.openai.com). Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`.

Switching providers is config-only — no rebuild needed.

---

## Example: Portainer GitOps stack with Traefik

This is the reference setup: a Portainer instance managing Docker on a homelab host, with Traefik handling TLS termination and routing. Portainer polls the Git repository and redeploys when the branch updates.

### Assumptions

- Traefik is already running and connected to a Docker network named `traefik`
- Traefik has a `websecure` entrypoint (port 443) and a `letsencrypt` certificate resolver
- Portainer is running and can reach the Docker socket

### Steps

1. **In Portainer** → Stacks → Add stack → Repository.

2. Set **Repository URL** to your fork/clone of this repo and **Compose path** to `docker-compose.prod.yml`.

3. Enable **GitOps updates** (either polling interval or webhook — webhook is lower latency).

4. Under **Environment variables**, add every required variable from the table above, plus the Traefik vars:

   ```
   POSTGRES_USER         jobfinder
   POSTGRES_PASSWORD     <strong random password>
   POSTGRES_DB           jobfinder
   SESSION_SECRET        <openssl rand -hex 32>
   OIDC_ISSUER           https://auth.yourdomain.com/application/o/job-finder/
   OIDC_CLIENT_ID        <from your provider>
   OIDC_CLIENT_SECRET    <from your provider>
   OIDC_REDIRECT_URI     https://jobs.yourdomain.com/api/auth/callback
   APP_DOMAIN            jobs.yourdomain.com
   CERT_RESOLVER         letsencrypt
   TRAEFIK_NETWORK       traefik
   LLM_PROVIDER          anthropic
   ANTHROPIC_API_KEY     <your key>
   ADZUNA_APP_ID         <your id>
   ADZUNA_APP_KEY        <your key>
   ```

5. Deploy. On first deploy the `migrate` service runs Alembic migrations before the API starts. Watch the logs — if any `:?` variable is missing the stack exits immediately with a clear error message.

6. Register your redirect URI with the OIDC provider (`https://jobs.yourdomain.com/api/auth/callback`) if you haven't already.

7. Navigate to `https://jobs.yourdomain.com` and sign in.

### Deploying with Terraform

If you manage your Portainer stacks with Terraform, use the [Portainer provider](https://registry.terraform.io/providers/portainer/portainer/latest):

```hcl
resource "portainer_stack" "job_finder" {
  name            = "job-finder"
  deployment_type = "standalone"
  method          = "repository"
  endpoint_id     = var.portainer_endpoint_id

  repository_url            = "https://github.com/yourname/job-finder"
  repository_reference_name = "refs/heads/main"
  file_path_in_repository   = "docker-compose.prod.yml"

  # Write-only credentials — not stored in Terraform state.
  git_repository_authentication     = true
  repository_username_wo            = var.git_username
  repository_password_wo            = var.git_token
  repository_credentials_wo_version = 1

  stack_webhook = true  # redeploy via webhook rather than polling

  env { name = "POSTGRES_USER";      value = var.postgres_user }
  env { name = "POSTGRES_PASSWORD";  value = var.postgres_password }
  env { name = "POSTGRES_DB";        value = var.postgres_db }
  env { name = "SESSION_SECRET";     value = var.session_secret }
  env { name = "OIDC_ISSUER";        value = var.oidc_issuer }
  env { name = "OIDC_CLIENT_ID";     value = var.oidc_client_id }
  env { name = "OIDC_CLIENT_SECRET"; value = var.oidc_client_secret }
  env { name = "OIDC_REDIRECT_URI";  value = var.oidc_redirect_uri }
  env { name = "APP_DOMAIN";         value = var.app_domain }
  env { name = "CERT_RESOLVER";      value = "letsencrypt" }
  env { name = "TRAEFIK_NETWORK";    value = "traefik" }
  env { name = "LLM_PROVIDER";       value = "anthropic" }
  env { name = "ANTHROPIC_API_KEY";  value = var.anthropic_api_key }
}
```

Keep sensitive values in `terraform.tfvars` (gitignored) or pull them from a secrets backend.

---

## Generic reverse proxy

If you're not using Traefik, remove the `labels` block and the `traefik` network from the `web` service in `docker-compose.prod.yml`, expose port 80 on the container, and point your reverse proxy at it:

```yaml
web:
  ...
  ports:
    - "8080:80"   # or bind to 127.0.0.1:8080:80
```

Then configure your proxy to:

- Terminate TLS and forward to port 8080
- Pass `X-Forwarded-For` and `X-Forwarded-Proto` headers

The nginx config inside the container proxies `/api/` to `api:8000` on the internal Docker network — your reverse proxy only needs to talk to nginx.

---

## Upgrades and migrations

Alembic migrations run automatically on every deploy via the `migrate` service. Pulling a new version of the code and redeploying is all that's needed; migrations are applied before the API starts. Downgrade scripts exist for every migration if a rollback is needed.

To run migrations manually:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate
```

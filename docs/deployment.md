# Deployment

SyntaxLab deploys as two independent pieces:

| Piece | Where (decided) | Artifact |
|---|---|---|
| Parser API | Hugging Face Space, Docker SDK | `services/parser-api/Dockerfile` |
| Web app | Vercel | `apps/web` (Next.js) |

The web app is a static-first Next.js site. Every analysis comes from the API, called directly
from the browser, so the API origin must be known when the web app is built (CSP and client
config), and the web origin must be allowed by the API (CORS).

> **Cost note (checked 2026-10-21 against the Hugging Face docs).** Creating a Docker Space now
> requires a paid Hugging Face plan (PRO for a personal account). The default *CPU Basic*
> hardware (2 vCPU, 16 GB RAM) has no hourly cost once you have that plan. If a paid plan is
> not an option, use one of the [alternatives](#alternatives): the image is the same.

## 1. The API image

```bash
docker build -t syntaxlab-api services/parser-api
docker run --rm -p 7860:7860 --cpus 2 --memory 4g syntaxlab-api
curl -s localhost:7860/ready
```

What the image does:

- Python 3.12 and CPU-only torch. Dependencies come from `uv.lock` (`uv sync --locked`), so
  the image matches what CI tests.
- **Models are baked in at build time** (`syntaxlab-api download-models`, about 430 MB for
  English), and the build fails if `syntaxlab-api check` does. At runtime nothing is
  downloaded, so a cold start costs only the model load.
- It runs as uid 1000 (`syntaxlab`), which Hugging Face Spaces require, on `PORT` (default
  7860).
- One uvicorn worker. Each worker would hold its own copy of the models. Concurrency is the
  per-language queue (see [architecture.md §6](architecture.md#6-model-lifecycle-and-concurrency)).
- `HEALTHCHECK` probes `/health` (liveness). `/ready` returns 503 until the models are loaded;
  use it for readiness checks and for smoke tests after a deploy.

### Configuration

All settings are environment variables; see [api.md](api.md#limits-defaults-per-language-overrides-in-languagesyaml).
Production needs only one:

| Variable | Value |
|---|---|
| `SYNTAXLAB_CORS_ORIGINS` | JSON list of web origins, e.g. `["https://syntaxlab.vercel.app"]` |

Useful to tune:

| Variable | Why |
|---|---|
| `SYNTAXLAB_CPU_THREADS` | Defaults to the CPU count. Set it to the CPUs actually granted if the platform reports more than you get |
| `SYNTAXLAB_RATE_LIMIT_PER_MINUTE` / `_BURST` | Per-client limit (60/min, burst 10) |
| `SYNTAXLAB_MAX_QUEUE`, `SYNTAXLAB_ANALYSIS_TIMEOUT_S` | Back-pressure: 503 when the queue is full, 504 on timeout |
| `FORWARDED_ALLOW_IPS` | See below |

### Client addresses behind a proxy

Rate limits are per client address. Behind a platform's reverse proxy, the address the API
sees is the proxy's, so uvicorn runs with `--proxy-headers` and reads `X-Forwarded-For`, but
only from proxies listed in `FORWARDED_ALLOW_IPS`. The image trusts loopback and the private
ranges (`10/8`, `172.16/12`, `192.168/16`), where platform proxies normally live.

Never set it to `*`. uvicorn would then take the leftmost `X-Forwarded-For` entry, which the
client writes itself, and anyone could bypass the rate limit by sending a different address
each time. If the platform's proxies use public addresses, every request would look like it
came from the proxy and share one rate-limit bucket. In that case list the proxy ranges the
platform publishes.

## 2. Hugging Face Space (API)

The Space is a separate git repository on huggingface.co. `deploy/huggingface/prepare-space.sh`
fills a checkout of it with `services/parser-api` (files git tracks; `.venv` and `.models` are
never copied), the Space README (`deploy/huggingface/README.md`, whose front matter sets
`sdk: docker` and `app_port: 7860`) and the licence.

One-time setup:

1. Create a Space: SDK **Docker**, hardware **CPU Basic**, visibility public. The API's
   source is open, and a private Space's URL is not reachable by the web app.
2. In **Settings → Variables**, add `SYNTAXLAB_CORS_ORIGINS` (see above). Spaces inject
   variables at runtime, and also pass them as build args, which this Dockerfile ignores.

Each deploy:

```bash
git clone https://huggingface.co/spaces/<owner>/<space> ../syntaxlab-space
deploy/huggingface/prepare-space.sh ../syntaxlab-space
cd ../syntaxlab-space
git add -A
git commit -m "Deploy SyntaxLab <commit>"
git push
```

Pushing triggers a build on Hugging Face. Then:

```bash
curl -s https://<owner>-<space>.hf.space/ready
```

The Space URL is `https://<owner>-<space>.hf.space` (the `SPACE_HOST` variable inside the
container). Expect `{"ready": true, …}` once the models are loaded.

Behaviour to know:

- **Sleeping.** On free hardware a Space goes to sleep when unused and wakes on the next
  request. While it starts, requests get Hugging Face's own response, not the API's. The web
  app reports "the analysis service cannot be reached", and a retry after the models load
  works. Paid hardware does not sleep.
- **Disk is not persistent.** That does not matter here: the API keeps no state, and models
  are in the image.
- **Outbound network** is limited to ports 80, 443 and 8080. The API makes no outbound
  requests at runtime.

## 3. Vercel (web app)

One-time setup, in a new Vercel project linked to the GitHub repository:

| Setting | Value |
|---|---|
| Root Directory | `apps/web` |
| Framework preset | Next.js (detected) |
| Install / build commands | defaults (pnpm is detected from the root `pnpm-lock.yaml`) |
| Environment variable | `NEXT_PUBLIC_SYNTAXLAB_API_URL` = `https://<owner>-<space>.hf.space` |

`NEXT_PUBLIC_SYNTAXLAB_API_URL` is read **at build time**. It is inlined into the client and
written into the Content-Security-Policy (`connect-src`). Changing it needs a redeploy, not
just a restart. If it is missing, the build points at `http://127.0.0.1:8710` and the deployed
site cannot reach any API.

After the first deploy, add the production origin to the Space's `SYNTAXLAB_CORS_ORIGINS`.

Preview deployments get their own URLs, which the production API does not allow. Either add a
stable preview alias to `SYNTAXLAB_CORS_ORIGINS`, or point previews at a second (staging)
Space with a preview-scoped `NEXT_PUBLIC_SYNTAXLAB_API_URL`.

### What the web app sends

Every page sends a static CSP (no nonces, so pages stay prerendered and cacheable), along with
`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` and `Permissions-Policy`. They
are defined in `apps/web/next.config.ts`. `e2e/security.spec.ts` checks that the headers are
present and that the policy blocks nothing the app uses, including PNG export (`blob:` and
`data:` images).

## 4. After a deploy

1. `GET <api>/ready` returns `ready: true`.
2. Open the site, analyze the first example sentence, switch to *Word relations*, export a PNG.
3. In the Algorithm Lab, parse a preset's example; in Practice, check one exercise.
4. The browser console shows no CSP violations and no CORS errors.

## Alternatives

The same image runs on any container platform. Budget **≥ 2 GB memory**: Stanza English uses
about 650 MB of working set on top of Python and torch. Use at least 2 vCPU for acceptable
latency.

- **Google Cloud Run.** `gcloud run deploy --source services/parser-api --cpu 2 --memory 4Gi
  --port 7860`. With `--min-instances 0` it scales to zero, and a cold start includes the model
  load. Use `/ready` as the startup probe.
- **Fly.io.** `fly launch --dockerfile services/parser-api/Dockerfile` with `internal_port =
  7860` and a `/ready` HTTP check. Auto-stop gives the same cold-start trade-off.

On any platform, set `SYNTAXLAB_CORS_ORIGINS`, and check `FORWARDED_ALLOW_IPS` against the
platform's proxy addresses.

## Measured

Web bundles (production build; gzip, JavaScript loaded by the page's HTML):

| Route | JS (gzip) |
|---|---|
| `/` (Analyzer) | 261 KB |
| `/lab` | 252 KB |
| `/learn` | 222 KB |
| `/about` | 188 KB |

Shared CSS is 10.6 KB gzip. About 160 KB of each figure is the React and Next.js runtime. The
analyzer adds d3-zoom and the diagram code, and Radix Tooltip loads only on the two pages that
use it.

API container, measured by the CI `image` job (GitHub-hosted runner, `--cpus 2 --memory 4g`,
2026-10-21):

| Measure | Value |
|---|---|
| Image size | 1.61 GB (torch CPU + Stanza + English models) |
| Start to `/ready` (includes model load) | ≈ 11 s |
| Memory after one parse | 860 MiB |
| First parse, short sentence, end to end | ≈ 1 s |

A single run on CI hardware, so treat these as indicative, not as a benchmark. Plan for at
least 2 GB of memory. On a host that sleeps or scales to zero, the first request after idle
waits for the start time above, plus the platform's own wake-up time.

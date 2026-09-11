# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CabinBook — appointment scheduling SaaS for independent practitioners (physiotherapists,
osteopaths, psychologists) in France, with automated email/SMS/WhatsApp reminders. Backend
is French-language throughout (models, docstrings, admin) — match that when editing
backend code.

## Stack

- **Backend**: Django 5.1 + Django REST Framework, JWT auth (`djangorestframework-simplejwt`), PostgreSQL 16, Celery + Redis (broker/result backend + beat scheduler), Stripe billing, SendGrid (email), Twilio (SMS/WhatsApp).
- **Frontend (praticien dashboard)**: `frontend-app/` — React 19 + Vite, plain JS (no TS), oxlint for linting. This is the active frontend; `frontend/` at the repo root is legacy/unused standalone HTML+JSX.
- **Public-facing pages** (landing, booking, annuaire, avis, mentions légales) are server-rendered Django templates in `templates/`, served directly by Django views in [cabinbook/views.py](cabinbook/views.py) — not part of the React app.

## Commands

All backend commands normally run inside the Docker web container in dev.

```bash
# Start the full dev stack (Postgres, Redis, Celery worker+beat, web)
docker compose -f docker-compose.dev.yml up --build

# Migrations
docker compose -f docker-compose.dev.yml exec web python manage.py migrate
docker compose -f docker-compose.dev.yml exec web python manage.py makemigrations

# Run all tests
docker compose -f docker-compose.dev.yml exec web pytest

# Run a single test file / test
docker compose -f docker-compose.dev.yml exec web pytest tests/test_core.py
docker compose -f docker-compose.dev.yml exec web pytest tests/test_core.py::test_appointment_confirm -v

# Django shell
docker compose -f docker-compose.dev.yml exec web python manage.py shell

# Same commands without Docker, if deps are installed locally (venv + requirements.txt):
python manage.py migrate
pytest
pytest --cov=apps --cov-report=xml -v   # matches CI in .github/workflows/ci.yml
```

Frontend (`frontend-app/`):

```bash
cd frontend-app
npm run dev       # Vite dev server, http://localhost:5173
npm run build
npm run lint       # oxlint
```

Test discovery/config is in [pytest.ini](pytest.ini): tests live under `tests/`, files named `test_*.py`. There is no per-app `tests.py` convention here — all backend tests are centralized in the top-level `tests/` directory.

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs `pytest --cov=apps` against real Postgres/Redis services, then deploys to the VPS over SSH on pushes to `main`.

## Architecture

### Django apps (`apps/`)

- **accounts** — `User` (custom user model, `AUTH_USER_MODEL`, email as `USERNAME_FIELD`), `Practitioner`, `Patient`. A `User` owns one or more `Practitioner`s (multi-practitioner support gated by plan — see below). Also owns cookie-based JWT auth.
- **appointments** — the core scheduling domain: `TimeSlot`, `AppointmentSeries` (recurring bookings), `Appointment`, `Review`, `SessionNote`, `WaitlistEntry`, `AvailabilityRule` (recurring weekly availability, feeds slot auto-generation). Each app has both an authenticated API (`urls.py`/`views.py`) and an unauthenticated "public" surface (`public_urls.py`/`public_views.py`) used by patients booking without an account.
- **billing** — `Invoice` model + Stripe checkout session creation and webhook handling.
- **notifications** — no models; `services.py` holds provider integrations (`EmailService` via SendGrid, `SmsService`/WhatsApp via Twilio), `tasks.py` holds the Celery tasks that call them (reminder emails/SMS/WhatsApp, daily slot generation from `AvailabilityRule`).

### Two authentication/authorization surfaces

Every domain app splits into an **authenticated practitioner-facing API** (`/api/...`, JWT-protected, used by the React dashboard) and a **public patient-facing API** (`/api/public/...`, no auth, used by the server-rendered booking/annuaire/avis pages' JS). Check both `views.py` and `public_views.py` when touching a feature — behavior often needs to change in both places (e.g. booking creates an `Appointment` from the public side but management/status transitions happen from the authenticated side).

### Auth mechanism

JWT tokens are issued via `CookieTokenObtainPairView`/`CookieTokenRefreshView` ([apps/accounts/views.py](apps/accounts/views.py)) and stored in **httpOnly cookies**, not returned in the response body. `CookieJWTAuthentication` ([apps/accounts/authentication.py](apps/accounts/authentication.py)) reads the `access_token` cookie instead of the `Authorization` header — this is the `DEFAULT_AUTHENTICATION_CLASSES` for all of DRF. Keep this in mind when writing or debugging API calls/tests: there's no bearer token to pass manually from the browser side.

### Plan-based gating

`User.plan` (`starter` / `pro` / `cabinet`) gates both feature access and account limits:
- `User.max_practitioners` caps how many `Practitioner`s an owner can create (1 / 1 / 5).
- SMS reminders are skipped entirely for `starter` plan (see `send_appointment_reminder_sms` in [apps/notifications/tasks.py](apps/notifications/tasks.py)); WhatsApp reminders additionally require `TWILIO_WHATSAPP_FROM_NUMBER` to be configured.
- Stripe price IDs per plan are in `settings.STRIPE_PRICES`.

When adding plan-gated features, follow this pattern rather than inventing a new one.

### Sensitive data encryption

`Patient.carte_vitale_number` (French social security number) uses `EncryptedCharField` ([apps/accounts/fields.py](apps/accounts/fields.py)) — a custom Django field that transparently encrypts with Fernet (`settings.FIELD_ENCRYPTION_KEY`) at the DB layer and decrypts on read. Application code (serializers, views) always sees plaintext; only the DB column is ciphertext. Use this field for any new sensitive PII rather than a plain `CharField`.

### Celery scheduling

`CELERY_BEAT_SCHEDULE` in [cabinbook/settings.py](cabinbook/settings.py) drives two daily jobs: `schedule_reminders_for_tomorrow` (10:00) and `generate_slots_from_availability` (06:00, expands `AvailabilityRule` into concrete `TimeSlot`s). Reminder-sending tasks are `bind=True, max_retries=3` and retry on failure with a 300s countdown — follow this pattern for new outbound-notification tasks.

### Tokens instead of auth for patient actions

`Appointment.confirmation_token` / `cancellation_token` (random, generated in `save()`) let patients confirm/cancel via a link in an email/SMS without logging in (`/book/confirm/{token}/`, `/book/cancel/{token}/`). Same pattern is used for `avis/<token>/` (review submission).

### URL structure

See [API_ROUTES.md](API_ROUTES.md) for the full authenticated API reference. Top-level routing is in [cabinbook/urls.py](cabinbook/urls.py): public HTML pages, `/api/auth/...`, `/api/{accounts,appointments,billing}/...` (authenticated), `/api/public/{book,directory}/...` (unauthenticated), `/book/<slug>/` (public booking page).

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
rtk uv run <cmd>        # Compact uv project command output
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
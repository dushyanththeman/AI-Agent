# DecaworkIT Agent

An AI-powered IT support agent that accepts natural-language requests and fulfills them by autonomously navigating a browser — clicking, typing, and interacting with the UI exactly like a human would. No DOM selectors. No API shortcuts. Just a real browser controlled by an LLM.

Built as a take-home assignment for [Decawork](https://decawork.ai) — a platform building AI agents for enterprise teams.

---

## Demo

> **Task 1:** "reset password for ashley25@example.com"
> The agent navigates to the admin panel, searches for the user, clicks through to the Reset Password page, fills in the email, and submits the form — fully autonomously.

> **Task 2:** "assign Pro license to kathleenshields@example.com"
> The agent navigates to the Users list, finds the user, opens their profile, and assigns the correct license from the dropdown — or detects the license is already assigned and reports back intelligently.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Entry Points                        │
│         test_agent.py  │  POST /tasks (FastAPI)         │
└──────────────────┬──────────────────┬───────────────────┘
                   │                  │
                   ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent Orchestrator                     │
│   Parses NL request → builds plan → executes steps      │
│              agent/core/orchestrator.py                 │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│               Browser Use Agent                         │
│   browser-use library + Groq              │
│   Opens real Chromium, navigates by clicking/typing     │
│              agent/core/browser_agent.py                │
└──────────────────────────┬──────────────────────────────┘
                           │  controls
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Flask Mock IT Admin Panel                  │
│   localhost:5050  —  Users, Reset Password, Audit Log   │
│              admin_panel/app.py                         │
└─────────────────────────────────────────────────────────┘
                           │  writes to
                           ▼
┌─────────────────────────────────────────────────────────┐
│                SQLite Audit Database                    │
│   Every action logged: actor, action, target, details   │
└─────────────────────────────────────────────────────────┘
```

### How it works

1. You give the agent a plain English instruction like `"reset password for ashley25@example.com"`
2. The **browser-use** library launches a real Chromium browser window
3. The Groq llama-3.3-70b-versatile LLM reads the visible page content...
4. The agent navigates the admin panel page by page, taking actions like a human operator would
5. Every completed action is recorded in the SQLite audit log with timestamp, actor, and details

The LLM never sees raw HTML or DOM structure — it only sees what a human would see on the screen. This is what makes it genuine computer-use, not automation scripting.

---

## Project Structure

```
decawork-it-agent/
│
├── agent/                          # Core agent + FastAPI server
│   ├── main.py                     # FastAPI app (POST /tasks, GET /tasks)
│   ├── config.py                   # Settings via pydantic-settings
│   ├── auth.py                     # API key middleware
│   ├── rate_limit.py               # SlowAPI rate limiting
│   ├── models.py                   # SQLAlchemy Task + AuditLog models
│   ├── database.py                 # DB session management
│   ├── schemas.py                  # Pydantic request/response schemas
│   ├── tasks.py                    # Celery task definitions
│   ├── queue.py                    # Celery app factory
│   └── core/
│       ├── browser_agent.py        # browser-use agent wrapper
│       ├── orchestrator.py         # Plan → execute → verify loop
│       ├── parser.py               # NL → structured intent (Groq)
│       ├── action_registry.py      # Maps intents to browser actions
│       └── prompts.py              # All LLM prompts as constants
│
├── admin_panel/                    # Flask mock IT admin panel
│   ├── app.py                      # Routes, models, seeding
│   └── templates/
│       ├── base.html
│       ├── users.html              # /admin/users — paginated list + search
│       ├── user_detail.html        # /admin/users/<id> — view/edit/delete
│       ├── reset_password.html     # /admin/reset-password
│       └── audit_log.html          # /admin/audit — filterable log table
│
├── screenshots/                    # Auto-saved per task_id
├── test_agent.py                   # Run two tasks end-to-end
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quickstart

### Prerequisites

- Python 3.11+
- - A Groq API key (get one free at console.groq.com — generous free tier, no credit card)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/decawork-it-agent.git
cd decawork-it-agent
python -m venv .venv
source .venv/bin/activate
pip install -r agent/requirements.txt
pip install -r admin_panel/requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```
GROQ_API_KEY=gsk_...
API_KEYS=your-secret-key
ADMIN_PANEL_URL=http://localhost:5050
```

### 3. Start the admin panel

```bash
cd admin_panel
python app.py
```

The panel runs at `http://localhost:5050/admin/users`. It auto-seeds 15 fake users on first run.

### 4. Run the agent

In a new terminal:

```bash
cd decawork-it-agent
source .venv/bin/activate
export GROQ_API_KEY=gsk_...
export PYTHONPATH=$(pwd)
python test_agent.py
```

A Chromium browser window will open and you'll watch the agent complete tasks autonomously.

---

## Example Tasks

These all work out of the box against the seeded mock panel:

```
"reset password for ashley25@example.com"
"assign Pro license to kathleenshields@example.com"
"create user newperson@corp.com with role member"
"delete user erin97@example.net"
"check if pamela64@example.net exists, if not create them, then assign Enterprise license"
```

### Via the FastAPI server

Start the API server:
```bash
cd agent
uvicorn main:app --reload --port 8000
```

Submit a task:
```bash
curl -X POST http://localhost:8000/tasks \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"request": "reset password for ashley25@example.com", "requester": "admin@company.com"}'
```

Poll for result:
```bash
curl http://localhost:8000/tasks/{task_id} \
  -H "X-API-Key: your-secret-key"
```

---

## Admin Panel Pages

| Route | Description |
|---|---|
| `GET /admin/users` | Paginated user list with email search |
| `GET /admin/users/<id>` | User detail — view, edit, delete, assign license |
| `POST /admin/users/create` | Create new user with email, name, role |
| `GET /admin/reset-password` | Password reset form |
| `GET /admin/audit` | Audit log — filterable by action type, paginated |

Every write action (create, delete, reset, assign license) is logged to the audit table with timestamp, actor, target, and details.

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| `POST` | `/tasks` | Submit a new IT task |
| `GET` | `/tasks` | List all tasks (paginated) |
| `GET` | `/tasks/{task_id}` | Get task status and result |
| `GET` | `/health` | Health check |

All endpoints require an `X-API-Key` header. Rate limits: 10 req/min on POST, 60 req/min on GET.

---

## Bonus Features

### Multi-step conditional logic

The agent handles compound instructions with branching logic:

```
"check if newuser@corp.com exists, if not create them, then assign a Pro license"
```

The orchestrator generates a step plan, executes each action, and routes based on the result — skipping steps that aren't needed (e.g. skipping "create" if the user already exists).

Run the conditional test suite:
```bash
python test_conditional.py
```

### Real SaaS panel (HubSpot)

The agent can operate against a real HubSpot CRM account. Add credentials to `.env`:

```
HUBSPOT_EMAIL=your@email.com
HUBSPOT_PASSWORD=yourpassword
```

Then submit a task with `"target": "hubspot"`:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "request": "create contact john@acme.com named John Smith at Acme Corp",
    "requester": "admin@company.com",
    "target": "hubspot"
  }'
```

The same agent, same orchestrator, different browser executor — no code changes needed.

### Slack trigger

The agent can be triggered from a Slack message:

```
@ITAgent reset password for ashley25@example.com
@ITAgent on hubspot create contact jane@corp.com named Jane Doe
/itagent check if newuser@corp.com exists, if not create them with Pro license
```

The bot responds immediately with a confirmation, runs the task async, then posts the result back to the channel with a step-by-step trace.

Setup: see [SLACK_SETUP.md](./SLACK_SETUP.md) for full instructions on creating the Slack app and configuring tokens.

---

## Key Design Decisions

**Why browser-use instead of raw Playwright?**
browser-use wraps Playwright with an LLM vision layer so the agent reasons about what it sees on the page, not the DOM structure. This is essential — the task spec explicitly forbids DOM selectors and API shortcuts. The agent navigates purely by reading visible content, just like a human.

**Why Groq llama-3.3-70b instead of OpenAI?**
Groq's free tier offers 14,400 requests/day with no credit card required, making it ideal for a demo project. Tasks run sequentially with a 10-second gap between them to stay within the 6,000 tokens/minute rate limit. `use_vision=False` disables screenshot encoding on every LLM call, cutting token usage by ~80% — the agent reads visible page text instead, which is sufficient for a simple admin panel.

**Why Celery + Redis for the API server?**
Browser automation is slow — a multi-step task takes 20-60 seconds. Synchronous HTTP endpoints would time out. Celery runs tasks in the background while the API returns a task ID immediately. The client polls for completion.

**Why Flask for the mock panel (not FastAPI)?**
The panel is a human-operated UI with forms and redirects — classic server-side rendering. Flask + Jinja2 is the right tool. FastAPI is reserved for the agent's programmatic API.

**Why SQLite for dev?**
Zero setup, file-based, works inside Docker. The same SQLAlchemy models work against PostgreSQL in prod by changing one env var.

---

## What I'd add with more time

- **Deploy to Railway** — one-click deploy with Redis and Postgres add-ons, publicly accessible URL for the Loom video
- **Screenshot replay** — a simple web UI to replay the agent's step-by-step screenshots for each task
- **More SaaS targets** — Notion workspace, Google Admin, Okta trial
- **MS Teams trigger** — parallel to Slack, same underlying task queue
- **Agent memory** — store user lookup results so repeat tasks on the same user are faster
- **Confidence threshold UI** — surface low-confidence tasks to a human for approval before execution

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for llama-3.3-70b-versatile |
| `API_KEYS` | Yes | Comma-separated API keys for the FastAPI server |
| `ADMIN_PANEL_URL` | Yes | URL of the Flask admin panel |
| `ADMIN_USERNAME` | Yes | Admin login username |
| `ADMIN_PASSWORD` | Yes | Admin login password |
| `REDIS_URL` | No | Redis URL for Celery (default: redis://localhost:6379/0) |
| `DATABASE_URL` | No | DB URL (default: sqlite:///./decawork.db) |
| `SCREENSHOT_DIR` | No | Where to save screenshots (default: ./screenshots) |
| `HUBSPOT_EMAIL` | No | HubSpot login for real SaaS target |
| `HUBSPOT_PASSWORD` | No | HubSpot password |
| `SLACK_BOT_TOKEN` | No | Slack bot token (xoxb-...) |
| `SLACK_SIGNING_SECRET` | No | Slack signing secret |
| `SLACK_APP_TOKEN` | No | Slack app token for socket mode (xapp-...) |

---

## Running with Docker Compose

```bash
cp .env.example .env
# fill in OPENAI_API_KEY and API_KEYS

docker-compose up --build
```

Services started:
- `admin_panel` → http://localhost:5050
- `agent_api` → http://localhost:8000
- `agent_worker` → Celery worker
- `flower` → http://localhost:5555 (Celery monitoring)
- `redis` → internal

---

## Tech Stack

| Layer | Technology |
|---|---|
| Browser agent | browser-use 0.1.40 |
| LLM | Groq llama-3.3-70b-versatile |
| Admin panel | Flask + Jinja2 + Bootstrap 5 |
| Agent API | FastAPI + Uvicorn |
| Task queue | Celery + Redis |
| Database | SQLAlchemy + SQLite / PostgreSQL |
| Rate limiting | SlowAPI |
| Fake data | Faker (fixed seed for reproducibility) |
| Containerisation | Docker Compose |






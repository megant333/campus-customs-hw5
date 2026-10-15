# Campus Customs — Multi-Agent Ticket Desk (Homework 5)

A five-agent PydanticAI team (boss, inventory, accountant, facilities, customer service) works the Campus Customs ticket board through a FastMCP server over a SQLite shop database. A FastAPI backend serves a React + Vite + TypeScript dashboard where you watch the agents work and approve payments as the human.

**This is a practice run:** no email is ever sent and no vendor is ever contacted. Customer replies stay on the board as drafts, and every payment needs a human approval.

```
React board (frontend/, :5173)  →  FastAPI (backend/main.py, :8000)  →  agent team (backend/*.py, gpt-6-luna)
                                                                     →  MCP server (mcp_server/server.py, stdio)  →  data/campus_customs_new.db
```

## What's in the repo

| Path | What it is |
|---|---|
| `data/campus_customs.db` | **Original** shop database. Never modified; used for resets. |
| `data/campus_customs_new.db` | **Working copy** that the tools update. It's committed in its resolved state after the Problem 9 run (all 3 tickets resolved, checking $160.00). |
| `mcp_server/server.py` | FastMCP server with 11 tools, the only path to shop data. Details in `mcp_server/README.md`. |
| `backend/` | Agents (`boss.py`, `inventory.py`, `accountant.py`, `facilities.py`, `customer_service.py`), `prompts/` (one per agent), `models.py`, `common.py`, `team.py`, `main.py` (FastAPI), `run_team.py` (CLI), `approve.py` (human approvals), `reset_db.py` |
| `frontend/` | React dashboard: ticket board, live agent lanes, pinball signal map, token sidebar, approvals, cash |
| `output/` | `harness.md` (full system reference), `design.md`, `desk_tickets.html` (expected vs actual, cash, reflection), `resolved_tickets.json`, `resolved_board.html` (screenshots), `audit_trail.json`, `mcp_smoke.json`, `github_url.txt` |
| `ai_prompts.md` | Log of every prompt used to build this |

## Setup (once)

You need **Python 3.11+**, **Node 20+**, and a **Portkey API key**.

```bash
git clone https://github.com/megant333/campus-customs-hw5.git
cd campus-customs-hw5

# Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Your key (the real .env is never committed)
cp .env.example .env        # then edit .env and set PORTKEY_API_KEY=...

# Frontend dependencies
cd frontend && npm install && cd ..
```

## 1. Copy the original database to the working copy (clean run)

Whenever you want to start clean, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
# or, equivalently, with an automatic backup to data/backups/ and a checksum check:
.venv/bin/python backend/reset_db.py
```

After a reset, all three tickets (101, 102, 103) are open and checking is **$3,400.00**.

## 2. Start the MCP server

You don't have to start it by hand: the backend (step 3) launches `mcp_server/server.py` itself over stdio and keeps one connection open for all five agents. To check the server on its own:

```bash
.venv/bin/python mcp_server/server.py        # runs the stdio MCP server (Ctrl+C to stop)
.venv/bin/python mcp_server/smoke_test.py    # calls each tool over MCP, writes output/mcp_smoke.json, restores the db
```

Using Claude Code? `.mcp.json` registers the same server (`campus-customs`) with relative paths. Open Claude Code in this folder and approve it.

## 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

The backend runs at http://localhost:8000, with interactive docs at http://localhost:8000/docs.

| Route | What it does |
|---|---|
| `GET /api/tickets` | Tickets with their status (open/pending/resolved), approvals, and drafts |
| `POST /api/tickets/{id}/run` | Runs the agent team on one ticket |
| `GET /api/events?since=` | Recent agent events (what each agent said, and which tools it used) |
| `GET /api/approvals` / `POST /api/approvals/{id}/decision` | Lists approvals / lets a **human** approve or reject a payment or PO (`{decision, decided_by, confirm: true}`) |
| `GET /api/cash` | Checking balance from `cash_accounts` |
| `POST /api/reset` | Resets the working db to the original values (`{confirm: true}`) |

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev          # opens http://localhost:5173
```

The board calls the backend at `http://localhost:8000`, and CORS allows `http://localhost:5173`. To use another backend port, run `VITE_API_URL=http://localhost:8001 npm run dev`.

## 5. Reset, then do the full three-ticket run

1. **Reset first:** click **Reset database** on the board, or run step 1. Checking should read $3,400.00, with all tickets open.
2. Select **#101** and press **Run agent team**. Do the same for **#102** and **#103**. Watch the agent lanes, the pinball signal map, and the token sidebar update live.
3. The team queues payments as pending approvals. In **Human approvals**, type your name and **Approve** (rent first, then invoice 501). Checking drops $3,400 → $1,000 → $160.
4. Press **Run follow-up** on any ticket that's still pending until all three show **✓ Resolved**.

You can also do it from the command line:

```bash
.venv/bin/python backend/run_team.py                   # FULL RUN: resets the db automatically, then works all open tickets
.venv/bin/python backend/approve.py                    # shows the board and pending approvals
.venv/bin/python backend/approve.py 2 approve --by "Your Name"
.venv/bin/python backend/run_team.py --continue        # finishes pending tickets after your decisions
```

Expected result (Problem 9):

| Ticket | Result | Cash |
|---|---|---|
| 101 Bulldog tee | Invoice 501 paid, which releases the size S reprint | −$840.00 |
| 102 Rent due | Rent paid on lease 1 | −$2,400.00 |
| 103 Bulk hoodie discount | $46.40/unit approved; the PO is refused (vendor 1 has an unpaid invoice) | $0.00 |

Checking goes **$3,400.00 → $160.00**.

Every agent step is appended to `output/audit_trail.json`, which is never wiped.

## Safety (enforced in the MCP server)

- **Human approval** is required for every payment, and agents can't approve.
- Cash can **never go negative**, and the shop never takes on debt.
- A vendor with an unpaid invoice won't ship new stock.
- **Dates** come from `desk.date_today`.
- **Amounts** come from the database, never from what an agent sends.
- **No outbound email or calls** exist; drafts stay on the board.
- Closed tickets are final.
- The original database is never opened by the server.

Full details are in `output/harness.md`.

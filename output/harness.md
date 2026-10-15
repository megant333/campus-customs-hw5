# Campus Customs Multi-Agent Harness

Living design notes for the Campus Customs multi-agent operation (a **practice run**: nothing is emailed, and no vendor or customer is ever contacted). It covers the **database tables, the 11 MCP tools, the five agents, the API routes, the dashboard, and the safety rules**, plus test and run evidence.

## Database

| File | Role |
|---|---|
| `data/campus_customs.db` | **Original.** Never modified. The MCP server and backend refuse to open it, and it is the source for resets. |
| `data/campus_customs_new.db` | **Working copy.** The MCP server, the backend, and the backend (`common.mcp_config()`) and `.mcp.json` point here, and the tools update it as tickets are worked. |
| `data/backups/` | `backend/reset_db.py` saves the previous working copy here before every reset, so a reset never loses anything. |

- **Shop "today"** is `desk.date_today` = 2026-08-31. Every overdue, due-soon, and ETA calculation uses it.
- **Reset:** run `.venv/bin/python backend/reset_db.py` (copy the original, then verify by SHA-256). A full team run resets automatically first.
- **Board tables** are added by the MCP server on first connect (`CREATE TABLE IF NOT EXISTS`); the original tables are never altered:
  - `approvals` (`id`, `kind` payment|purchase_order, `ticket_id`, `pay_kind` rent|invoice, `ref_id`, `period_due`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `amount_basis`, `rationale`, `prepared_by`, `status` pending|approved|rejected, `created_at`, `decided_by`, `decided_at`, `decision_reason`, `payment_id`, `expected_date`). This is the human approval queue; every payment passes through it.
  - `customer_messages` (`id`, `ticket_id`, `recipient`, `subject`, `body`, `status` CHECK = 'draft', `prepared_by`, `created_at`). This is the board, where drafts stay and are never sent.

## Tables

### `desk`
- **Fields:** `date_today` (TEXT), `notes` (TEXT)
- **Why it matters:** The shop's clock. Agents must use `date_today` (not the real date) to judge whether bills are overdue or due soon.

### `inventory`
- **Fields:** `sku` (TEXT), `name` (TEXT), `size` (TEXT), `qty` (INTEGER), `location` (TEXT); primary key (`sku`, `size`)
- **Why it matters:** Ground truth for what can actually be sold. Agents check stock per SKU and size before promising an order, and decrement `qty` when they fulfill one.

### `pricing`
- **Fields:** `sku` (TEXT, PK), `unit_cost` (REAL), `list_price` (REAL)
- **Why it matters:** Gives the margin floor. Any discount or price-override decision must stay above `unit_cost`.

### `vendors`
- **Fields:** `id` (INTEGER, PK), `name` (TEXT), `specialty` (TEXT), `lead_days` (INTEGER)
- **Why it matters:** Tells agents who can restock what and how fast. They use it to quote realistic restock dates and to match each invoice to a supplier.

### `leases`
- **Fields:** `id` (INTEGER, PK), `space_name` (TEXT), `landlord` (TEXT), `monthly_rent` (REAL), `next_due` (TEXT), `notes` (TEXT)
- **Why it matters:** Rent is the shop's largest fixed obligation. Agents use it to confirm that a rent notice is legitimate (correct landlord and amount) before paying.

### `cash_accounts`
- **Fields:** `name` (TEXT, PK), `balance` (REAL), `date` (TEXT)
- **Why it matters:** The spending limit. Before paying anything, an agent must confirm the balance covers the payment, and it must reduce the balance once the payment goes through.

### `payments`
- **Fields:** `id` (INTEGER, PK), `kind` (TEXT), `ref_id` (INTEGER), `amount` (REAL), `account` (TEXT), `paid_at` (TEXT), `approved_by` (TEXT)
- **Why it matters:** The audit trail. Every payment an agent makes must be logged here. `kind` plus `ref_id` points to the lease or invoice being paid, and `approved_by` records who signed off. The table is empty at the start.

### `invoices`
- **Fields:** `id` (INTEGER, PK), `vendor_id` (INTEGER, FK → `vendors.id`), `amount` (REAL), `due_date` (TEXT), `status` (TEXT), `description` (TEXT)
- **Why it matters:** Lists the money owed to suppliers. Agents check `status` and `due_date` to decide which bills to pay, and an unpaid invoice can block a restock.

### `tickets`
- **Fields:** `id` (INTEGER, PK), `type` (TEXT), `requester` (TEXT), `subject` (TEXT), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `lease_id` (INTEGER, FK → `leases.id`), `invoice_id` (INTEGER, FK → `invoices.id`), `status` (TEXT), `notes` (TEXT), `created_at` (TEXT)
- **Why it matters:** The work queue. Each ticket is a request an agent must route by `type` and resolve, and its links point to the inventory, lease, or invoice rows the agent needs.

## How the three open tickets link to other tables

| Ticket | Type | Links | What the links reveal |
|---|---|---|---|
| **101** Tauhid Zaman, Bulldog tee | `customer_order` | `sku`+`size` → `inventory` (CC-TEE-WHITE, S); `sku` → `pricing`; `invoice_id` 501 → `invoices` → `vendor_id` 1 → `vendors` (Bulldog Print Co) | Size S has **0 in stock**. Invoice 501 ($840, "Rush reprint CC-TEE-WHITE S") is still **open and past due** (due 2026-08-28). The order can't ship until the vendor is paid and reprints, which takes 5 lead days. |
| **102** Elm City Properties, Rent due | `rent_notice` | `lease_id` 1 → `leases` (Chapel Street shop) | The landlord and amount match the lease ($2,400, due 2026-09-02, 2 days from `date_today`). Paying it means a `payments` row (`kind` = rent, `ref_id` = 1) and a debit to `cash_accounts`. |
| **103** Yale AI Club, Bulk hoodie discount | `price_override` | `sku`+`size` → `inventory` (CC-HOOD-NAVY, M); `sku` → `pricing`; no lease or invoice | The club wants 20, but only **8 size M are in stock**. Any discount has to stay above the $22 unit cost (list price is $58). The shortfall could be reprinted through vendor 1. |

**Cash check:** checking has $3,400. Paying both rent ($2,400) and invoice 501 ($840) totals $3,240, which leaves just **$160**. Agents need to watch the balance closely and get approval before spending.

## MCP Server (`mcp_server/server.py`): every tool and the tables it uses

MCP is the **only** path to shop data. The backend never opens the database itself: even the ticket prefetch and the human approval desk go through MCP tools. The server is launched from `.mcp.json` over stdio.

| # | Tool | Mode | Used by | Reads tables | Writes tables |
|---|---|---|---|---|---|
| 1 | `get_ticket_context(ticket_id?, statuses?)` | read | harness prefetch (ticket row injected into every agent) | `desk`, `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`, `cash_accounts`, `approvals`, `customer_messages` | — |
| 2 | `check_stock(sku, size?, needed_qty?)` | read | inventory | `desk`, `inventory`, `pricing`, `vendors`, `invoices`, `approvals` | — |
| 3 | `get_finances()` | read | accountant | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases`, `approvals`, `payments` (10 most recent + each lease's last period paid) | — |
| 4 | `quote_margin(sku, qty, unit_price? \| discount_pct?)` | read | accountant | `pricing` | — |
| 5 | `get_lease_status(lease_id)` | read | facilities | `desk`, `leases`, `payments`, `approvals` | — |
| 6 | `get_board()` | read | humans (`approve.py`, Claude Code) | `desk`, `tickets`, `approvals`, `customer_messages`, `cash_accounts`, `invoices`, `leases` | — |
| 7 | `resolve_ticket(ticket_id, status, note, fulfill_order?, approved_unit_price?)` | write | boss | `desk`, `tickets`, `pricing`, `inventory`, `approvals` | `tickets` (status, notes), `inventory` (qty, only on full fulfilment) |
| 8 | `request_payment_approval(pay_kind, ref_id, rationale, prepared_by, ticket_id?)` | write | accountant | `desk`, `leases`, `invoices`, `cash_accounts`, `approvals`, `tickets` | `approvals` (pending row), `tickets` (note) |
| 9 | `request_purchase_order(vendor_id, sku, size, qty, rationale, prepared_by, ticket_id?)` | write | accountant | `desk`, `vendors`, `inventory`, `pricing`, `invoices`, `approvals`, `cash_accounts`, `leases`, `tickets` | `approvals` (pending prepaid PO), `tickets` (note) |
| 10 | `draft_customer_message(ticket_id, subject, body, prepared_by)` | write | customer service | `desk`, `tickets` | `customer_messages` (draft only) |
| 11 | `decide_approval(approval_id, decision, decided_by, reason?)` | write | **humans only** (in no agent's allowlist) | `desk`, `approvals`, `cash_accounts`, `invoices`, `leases`, `vendors` | `approvals` (decision), `payments` (new row), `cash_accounts` (debit), `invoices` (status → paid), `leases` (`next_due` + 1 month), `tickets` (note) |

**How the database updates as tickets are worked:**
1. An agent queues a payment or PO, which adds a pending `approvals` row and a ticket note.
2. A human approves through `decide_approval`. In one transaction this adds a `payments` row, debits `cash_accounts`, marks the invoice `paid` or moves the lease's `next_due` forward (for a PO, it records `expected_date`), and adds a ticket note.
3. The boss's `resolve_ticket` sets the ticket's final status and, on a full fulfilment, decrements `inventory`.

`pay_bill` from Problem 3 no longer exists as a tool. Money only moves inside `decide_approval`.

## Agents (`backend/`)

| Agent | File / prompt | MCP tools it can see | Tables reachable through them | Output | Effort / max tokens | Code guards |
|---|---|---|---|---|---|---|
| **boss** | `boss.py` / `prompts/boss.md` | `resolve_ticket` (once) | `tickets`, `inventory`, `pricing`, `approvals` | `TicketDecision` | medium / 6000 | Its reported status must equal what `resolve_ticket` wrote. It can't be `resolved` while `needs_human` is non-empty, and the `ticket_id` must match. **Resolved = the team's work is done:** every approval decided, the customer draft on the board, and only outside waits left (restock ETA, customer reply) noted with dates. |
| **inventory** | `inventory.py` / `prompts/inventory.md` | `check_stock` | `inventory`, `pricing`, `vendors`, `invoices`, `approvals` | `InventoryReport` | low / 4000 | `can_fulfil_now` must equal "every shortfall is 0". |
| **accountant** | `accountant.py` / `prompts/accountant.md` | `get_finances`, `quote_margin`, `request_payment_approval`, `request_purchase_order` | `cash_accounts`, `invoices`, `leases`, `pricing`, `vendors`, `inventory`, `approvals` | `FinanceReport` | low / 4000 | A recommended price must keep margin at or above 50%. |
| **facilities** | `facilities.py` / `prompts/facilities.md` | `get_lease_status` | `leases`, `payments`, `approvals` | `FacilitiesReport` | low / 4000 | It never recommends `pay` when the notice doesn't match the lease or the period is already queued or paid. |
| **customer_service** | `customer_service.py` / `prompts/customer_service.md` | `draft_customer_message` (once) | `customer_messages`, `tickets` | `CustomerDraft` | none / 1500 | The draft must be 130 words or fewer. Drafts are never sent. |

- **Model:** every agent uses `gpt-6-luna` through the user's Portkey gateway, on the OpenAI Responses API, hardcoded.
- **Delegation:** a single `delegate(to, request)` tool reaches any teammate (full mesh). There is no self-delegation, no cycles, and a maximum depth of 3; at depth 3 the tool is hidden by `prepare`. A teammate that fails comes back to its caller as a tool failure, so the caller can adapt instead of the whole run crashing.
- **Once-only tools** disappear after their first successful call: no double writes, and their schemas stop costing tokens.

### Run workflow
```bash
.venv/bin/python backend/run_team.py              # FULL RUN: auto-reset to original (backup kept), work all open tickets
.venv/bin/python backend/approve.py               # human: see board, approvals (priority order), drafts
.venv/bin/python backend/approve.py 2 approve --by "Megan Tachev"   # pays only if cash covers it
.venv/bin/python backend/run_team.py --continue   # team finishes open + pending tickets after decisions
.venv/bin/python backend/reset_db.py              # manual reset at any time
```
Dry runs: add `--db <scratch copy> --audit <scratch audit>` to keep the real working copy and audit trail clean.

## Backend API Routes (`backend/main.py`, FastAPI)

Start: `cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000`, then open http://localhost:8000 (interactive docs at `/docs`). Every route reaches shop data through the shared campus-customs MCP connection.

- `GET  /api/health` — reports that the server is up, plus the database and model it uses and whether a run is in progress.
- `GET  /api/tickets` — lists every ticket with its status (open/pending/resolved/declined), an `is_open` flag, and its approvals and drafts.
- `POST /api/tickets/{id}/run` — runs the five-agent team on one ticket and returns the boss's decision, the delegations, and token usage. One run at a time (409 if busy or the ticket is closed).
- `GET  /api/events?since=&limit=&ticket_id=` — returns recent agent events from `audit_trail.json`: what each agent said and which tools it used. Poll with `since=<next_since>` to get only new events.
- `GET  /api/approvals` — lists approvals (pending first, in payment-priority order) with the checking balance and available cash.
- `POST /api/approvals/{id}/decision` — a **human** approves or rejects a payment or PO. The body is `{decision, decided_by, confirm: true, reason?}`. Agent role names are refused, cash is re-checked (auto-reject if short), and the decision is logged to the audit trail.
- `GET  /api/cash` — returns the current checking balance from `cash_accounts`, plus available-for-new-spending and committed outflows.
- `POST /api/reset` — resets the working database to the original values (body `{confirm: true}`; the previous copy is backed up first). Blocked during a run.

Route guardrails:
- an `asyncio` lock allows one agent run or reset at a time;
- `confirm: true` is required on the routes that move money or reset the database;
- CORS allows only `localhost` origins;
- the routes never open the database themselves.

Verified on a scratch copy, launched as above but on port 8001, because port 8000 was taken by the hw-4 backend:
- Ticket 102 went to pending with approval #1. The approval was refused without confirm, refused for the "accountant" name, and refused for a bad id. A human then approved it (checking 3400 → 1000), and a second approval of the same request was refused.
- A follow-up `/run` resolved ticket 102, and another `/run` was then refused as already resolved.
- A concurrent run and a reset during a run both returned 409. A reset without confirm was refused, and a reset with it brought all tickets back to open and checking back to $3,400.

## Frontend Dashboard (`frontend/`, React + Vite + TypeScript)

- **Start:** `cd frontend && npm run dev`, which opens http://localhost:5173. It calls the backend directly at `http://localhost:8000`; CORS allows `http://localhost:5173` and `http://127.0.0.1:5173`.
- **Uses these routes:**
  - `/api/tickets` (board)
  - `/api/tickets/{id}/run` (Run / Run follow-up)
  - `/api/events?since=` (live lanes, timeline, pinball, tokens; polled every 1 s during a run)
  - `/api/approvals` and `/api/approvals/{id}/decision` (human approval panel)
  - `/api/cash` (balance card)
  - `/api/reset`
- **Design choices** are in `output/design.md`: the pinball signal-map sidebar, the token sidebar, and the cream liquid-glass theme.

## Problem 9 — Real Run Results (`data/campus_customs_new.db`)

**Steps:**
1. Reset through `POST /api/reset` (verified identical to the original). **Start checking: $3,400.00.**
2. First pass on 101, 102, and 103 from the React dashboard.
3. The human (Megan Tachev) approved both queued payments, rent first.
4. Follow-up runs until every ticket was resolved.

| Ticket | Runs | Final | Outcome | Cash |
|---|---|---|---|---|
| 101 Bulldog tee | 2 | resolved | Invoice 501 (the rush reprint) paid via approval #1; ETA 2026-09-05; draft #1 offers M, L, XL | −$840.00 |
| 102 Rent due | 3 | resolved | Lease verified; rent paid via approval #2 (payment #1); next due 2026-10-02 | −$2,400.00 |
| 103 Bulk hoodie | 1 | resolved | $46.40/unit approved (52.6% margin); 8 of 20 in stock; 12-unit PO refused by the vendor-block rule; draft #2 | $0.00 |

- **End checking: $160.00** = 3,400 − 2,400 − 840, matching `cash_accounts`.
- **Tokens:** 98,721 (90,879 in / 7,842 out) over 48 model calls, matching `audit_trail.json` and the dashboard token sidebar.
- **Fixes found during the real run:**
  1. "Resolved" was redefined as "the team's work is done". The frozen shop date means stock never arrives and customers never reply, so tickets could never resolve otherwise.
  2. `get_finances` now lists the payments ledger. Without it, ticket 102's first follow-up couldn't confirm the rent had posted.
  3. `/api/events` now passes along the tokens from final-answer model calls. The sidebar had been undercounting, and my Problem 8 check had compared it against that same filtered route.
- **Outputs:**
  - `output/desk_tickets.html`: Actual sections, expected-vs-actual comparison, and the Cash tab.
  - `output/resolved_tickets.json`
  - `output/resolved_board.html`: dashboard screenshots.
  - `output/audit_trail.json`: 128 records from the real run.

## Safety Rules and Guardrails

**Required rules, and where each is enforced:**

| Rule | Enforced in |
|---|---|
| `desk.date_today` is "today" for the shop. Overdue, due-soon, and ETAs use it, never the real clock. | Server (every date calculation reads `desk`); the shop date is injected into every agent's instructions |
| Vendor lead times come from `vendors.lead_days`. | Server: `check_stock` ETA = date_today + lead_days; PO `expected_date` is set at approval |
| A vendor won't ship new product while it has an open unpaid invoice. | Server: `check_stock.ships_new_product`; `request_purchase_order` and `decide_approval` both refuse a PO to that vendor |
| **Every payment needs human approval**, and the relevant tables are updated. | Server: no direct pay tool. `decide_approval` is in no agent's allowlist, refuses agent role names, and refuses the preparer; it updates `payments`, `cash_accounts`, `invoices`, `leases`, `approvals`, and `tickets` in one transaction |
| Not enough cash means the payment is rejected: no negative balance and no debt, and only cash going out is counted. | Server: `request_payment_approval` refuses if checking minus pending payments can't cover it; `request_purchase_order` refuses above `available_for_new_spending`; `decide_approval` **auto-rejects** if checking is short at decision time. POs are prepaid, so no payables are created. Expected sales revenue is ignored. |
| Reset the database to the original values before a full run. | `run_team.py` full mode calls `reset_db.reset()`, which backs up, copies, and verifies by SHA-256 |
| Never email customers or call vendors. All drafts stay on the board. | No send, email, or network tool exists on the server; `customer_messages.status` has `CHECK = 'draft'`; the backend loads **only** the `campus-customs` server from `.mcp.json` (never the workspace's Outlook server); prompts state it's a practice run |

**Extra guardrails, as a typical online multi-agent shop would have:**
- **Separation of duties:** the agent that prepares a payment can't approve it, and humans decide through a different tool than the one agents use.
- **Least privilege:** each agent sees only one to four MCP tools, and no agent has `decide_approval` or any payment tool.
- **Prompt-injection defense:** ticket text is labeled untrusted in every agent's instructions. Payees and amounts come only from the database (tools take no amount or payee argument), and facilities flags mismatched senders as possible fraud.
- **Idempotency and duplicates:** there's no second pending request for the same bill or PO, no paying the same rent period twice, no prepaying rent more than 10 days early, closed tickets are final, and once-only tools are hidden after use.
- **Integrity:** every write is a single SQLite transaction. Inventory never goes negative, and orders ship complete or not at all. Prices must stay between `unit_cost` and `list_price`, and a ticket can't be `resolved` while approvals are pending.
- **Input limits:** notes are capped at 800 characters, drafts at 1,200, PO qty must be 1–500, and quantities and prices must be positive.
- **Original-database protection:** the server and backend refuse any path to `campus_customs.db`.
- **Kill switch:** `CAMPUS_CUSTOMS_READ_ONLY=1` disables every write tool.
- **Budget caps:** per ticket, the whole delegation tree shares `UsageLimits(request_limit=30, tool_calls_limit=40, total_tokens_limit=80000)`, plus per-agent `max_tokens`.
- **Fault isolation:** a failed teammate returns a tool failure to its caller, and a failed ticket doesn't stop the remaining tickets. Both are logged.
- **Output validators** catch inconsistent reports before they spread downstream.
- **Human-readable board:** `approve.py` lists pending approvals in payment-priority order (rent → invoices → POs) with each amount's database basis, plus every draft.

## Audit Trail (`output/audit_trail.json`)

- **Append-only:** one JSON array that **only grows** and is never wiped between runs. Each record is written the moment its step happens, using an atomic rewrite. If the file is ever unreadable, it is set aside rather than overwritten.
- **Every record has:** `run_id`, `seq`, `logged_at`, `shop_date`, `database`, `ticket_id`, `agent`, `chain` (the delegation path), `step`, and `event`.
- **Events:**
  - `run_start` / `run_end`: mode, ticket list, reset info, totals, failed tickets.
  - `agent_start`: the request the agent received.
  - `model_response`: every tool call with its arguments, any text, tokens in and out, and the finish reason. There is one per model call.
  - `tool_results`: what came back (MCP and delegation), whether it succeeded, failed, or was retried, with content truncated to 2,000 characters.
  - `agent_end`: the typed output and its usage.
  - `error`: any exception.
  - `human_decision`: each `approve.py` decision, including refusals.
- No API keys are ever logged.
- Real-run trail: the reset, 6 team runs, and 2 human decisions are all appended (128 records after Problem 9).
- It has already paid for itself: the trail showed exactly why ticket 102 didn't resolve, why the accountant passed `unit_price=0`, and why customer service ran out of tokens. All three were fixed before the first real run.

## Token-Cost Design

- The ticket row and its board state are fetched once through MCP and injected into every agent, so no agent spends a call reading the ticket.
- Each agent sees only a minimal tool list, and once-only tools are hidden after use. Tool schemas are resent on every request.
- Tools return a lot per call. `check_stock` gives stock, shortfall, vendors, ETAs, ship blocks, and covering invoices in one call, and `get_finances` gives the whole cash picture.
- The specialists run at low reasoning effort, the boss at medium, and customer service at none.
- The boss copies numbers from reports instead of reasoning about arithmetic, and delegation requests are self-contained so nobody re-fetches facts.
- Follow-up runs only redo work whose state changed.

| Run (all on scratch copies) | Requests | Input tokens | Output tokens | Notes |
|---|---|---|---|---|
| v1: boss-only routing (Problem 5) | 41 | 68,857 | 5,958 | Ordered a duplicate tee reprint |
| v3: full mesh (Problem 5) | 31 | 46,423 | 4,294 | Before the safety rules |
| v4: safety rules, first pass | 33 | 55,457 | 8,760 | Customer service hit its token cap (4,000 wasted); fixed with effort `none` |
| v4: follow-up pass after approvals | 19 | 38,565 | 4,027 | 102 resolved, 101 waiting on restock, 103 re-checked |
| **final: first pass** | **33** | **56,175** | **4,690** | No errors; 101 pays invoice 501 (pending), 102 rent queued, 103 at $46.40 with the PO refused (vendor 501 block). 79 audit records |

## Test Evidence

- **`output/mcp_smoke.json`: 12/12 pass.** Reads were checked against direct SQLite queries. The checks: the PO was refused because vendor 1 has open invoice 501; rent was queued with no money moved; the accountant was refused as approver; a human approval paid out (3400 → 1000); duplicate rent was refused (not prepayable until 10 days before due); a below-cost price and shipping without stock were refused; and a draft was saved with `sent=False`. The working copy was restored byte-identical.
- **Dry-run cycle** (full run → human approvals → follow-up):
  1. **101:** pays invoice 501, then stays pending for the restock expected 2026-09-05. The draft offers M, L, and XL.
  2. **102:** the notice is verified, rent approval goes to the human, the human approves, and the ticket is **resolved**. `leases.next_due` moved to 2026-10-02.
  3. **103:** $46.40 per unit (20% off, 52.6% margin, $928). There are 8 of 20 in stock. No PO is possible: first vendor 1 was blocked by invoice 501, and after it was paid, $264 > $160 available. The ticket waits on the customer's choice.

  Checking ended at **$160 and never went negative**. The agent approver was refused.

## History

- **Problem 2:** studied the database, made the working copy, and started this harness.
- **Problem 3:** created the MCP server with 3 tools.
- **Problem 4:** connected it to Claude Code and smoke-tested it.
- **Problem 5:**
  - built the five-agent PydanticAI team with full-mesh delegation and gpt-6-luna;
  - grew the server to 11 tools, moved the working copy to `data/`, and added the reset, the approval-only payments, the audit trail, and the safety rules above.
- **Problem 6:** wrote `output/desk_tickets.html` with the expected behavior for each ticket.
- **Problem 7:** added the FastAPI backend routes for the React dashboard.
- **Problem 8:** built the React agent dashboard with the pinball signal map, the token sidebar, and live agent lanes (see `output/design.md`).
- **Problem 9:** reset the database, ran all 3 tickets to resolved with 2 human approvals (checking $3,400 → $160), filled the desk page's Actual and Cash sections, and wrote `resolved_tickets.json` and `resolved_board.html`.
- **Problem 11:** pushed to https://github.com/megant333/campus-customs-hw5 (public). Both databases are under `data/`, the real `.env` is excluded (`.env.example` is provided), and launch paths are portable. A fresh clone was tested: install, smoke test 12/12, board build, and backend reset.

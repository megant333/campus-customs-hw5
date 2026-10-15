# Campus Customs MCP Server

## Purpose

This server is the **only** way the Campus Customs agent team (and the humans supervising it) reads or changes shop data. It handles a practice-run ticket desk: customer orders, rent notices, and price-override requests. Agents never write SQL. Every tool:

- returns only real database rows (missing data comes back as `null`, never a guess),
- takes money amounts, payees, and dates from the database instead of trusting the caller,
- checks every business and safety rule before writing, and writes nothing if a check fails,
- does all of its writes in a single SQLite transaction.

The server is built with [FastMCP](https://gofastmcp.com) and uses stdio transport. It is launched from `hw-5/.mcp.json` (and from the workspace-root `.mcp.json` for Claude Code).

## Database

- **Uses:** `../data/campus_customs_new.db`, the working copy that the tools update as tickets are worked.
- **Never opens:** `../data/campus_customs.db`, the original. The server refuses any path to it, and it is the source for resets.
- **Reset:** `../.venv/bin/python ../backend/reset_db.py` (the previous copy is backed up to `data/backups/`).
- **Override:** set `CAMPUS_CUSTOMS_DB` to use a scratch copy, for example for dry runs.
- **Shop date:** all dates come from `desk.date_today`, never the system clock.
- **Board tables** are created on first connect if missing; the original tables are never altered:
  - `approvals`: the human approval queue for payments and prepaid purchase orders.
  - `customer_messages`: draft replies. `status` can only be `'draft'`.

## Tools (11)

| # | Tool | Mode | Used by | Tables read | Tables written |
|---|---|---|---|---|---|
| 1 | `get_ticket_context(ticket_id?, statuses?)` | read | harness prefetch, Claude Code | desk, tickets, inventory, pricing, invoices, vendors, leases, cash_accounts, approvals, customer_messages | — |
| 2 | `check_stock(sku, size?, needed_qty?)` | read | inventory | desk, inventory, pricing, vendors, invoices, approvals | — |
| 3 | `get_finances()` | read | accountant | desk, cash_accounts, invoices, vendors, leases, approvals, payments | — |
| 4 | `quote_margin(sku, qty, unit_price? \| discount_pct?)` | read | accountant | pricing | — |
| 5 | `get_lease_status(lease_id)` | read | facilities | desk, leases, payments, approvals | — |
| 6 | `get_board()` | read | humans | desk, tickets, approvals, customer_messages, cash_accounts, invoices, leases | — |
| 7 | `resolve_ticket(ticket_id, status, note, fulfill_order?, approved_unit_price?)` | write | boss | desk, tickets, pricing, inventory, approvals | tickets, inventory |
| 8 | `request_payment_approval(pay_kind, ref_id, rationale, prepared_by, ticket_id?)` | write | accountant | desk, leases, invoices, cash_accounts, approvals, tickets | approvals, tickets |
| 9 | `request_purchase_order(vendor_id, sku, size, qty, rationale, prepared_by, ticket_id?)` | write | accountant | desk, vendors, inventory, pricing, invoices, approvals, cash_accounts, leases, tickets | approvals, tickets |
| 10 | `draft_customer_message(ticket_id, subject, body, prepared_by)` | write | customer service | desk, tickets | customer_messages |
| 11 | `decide_approval(approval_id, decision, decided_by, reason?)` | write | **humans only** | desk, approvals, cash_accounts, invoices, leases, vendors | approvals, payments, cash_accounts, invoices, leases, tickets |

**What each tool adds:**
- `check_stock` reports `ships_new_product` for each vendor (false while it has an open unpaid invoice), each vendor's `earliest_restock_date` (shop date + `lead_days`), and `open_invoices_for_item` (a restock that is already ordered and only needs paying).
- `get_finances` also lists the 10 most recent payments and each lease's `last_period_paid` (with its `payment_id`). It reports `committed_outflows` and `available_for_new_spending` (checking minus open invoices, rent due within 10 days, and pending POs).
- `decide_approval` is the only place money moves. On approval it inserts a `payments` row, debits checking, marks the invoice paid (rent: `next_due` + 1 month; PO: records `expected_date`), and notes the ticket. If cash is short at decision time, it **auto-rejects**.

`pay_bill` (Problem 3) was removed: payments can't bypass human approval.

## Safety enforced in code

- **Human approval for every payment.** `decide_approval` is in no agent's allowlist, refuses agent role names as `decided_by`, and refuses the preparer.
- **No negative cash and no debt.** Payment requests must fit checking after other pending payments. POs are prepaid and must fit `available_for_new_spending`. Incoming revenue is never counted.
- **Vendor blocks:** no PO to a vendor with an open unpaid invoice, at either the request or the decision step.
- **Duplicates:** no duplicate pending requests, no paying the same rent period twice, and no queuing rent more than 10 days before due.
- **Tickets:** closed tickets are final, and a ticket can't be `resolved` while it has pending approvals.
- **Stock and prices:** orders ship complete or not at all, so inventory never goes negative. Prices must stay between `unit_cost` and `list_price`.
- **Input limits:** notes up to 800 characters, drafts up to 1,200, PO qty 1–500.
- **No outbound communication:** no email or network tools exist, and drafts stay on the board.
- **Kill switch:** `CAMPUS_CUSTOMS_READ_ONLY=1` disables every write tool.

## Running and testing

```bash
../.venv/bin/python server.py          # normally started by .mcp.json, not by hand
../.venv/bin/python smoke_test.py      # 12 MCP calls over stdio -> ../output/mcp_smoke.json (db restored after)
```

Dependencies are listed in `../requirements.txt`.

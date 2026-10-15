"""Smoke test for the Campus Customs MCP server.

Launches the server over stdio with the same launch config the backend uses, calls each tool over the MCP protocol, cross-checks the returned
values against direct sqlite3 queries of campus_customs_new.db, and writes the
evidence to output/mcp_smoke.json.

The tools run against a temporary copy of the original data/campus_customs.db, so the
results are the same on every machine, and data/campus_customs_new.db is never touched.

Run:  .venv/bin/python mcp_server/smoke_test.py   (from hw-5/)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from fastmcp import Client

HW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW / "backend"))
from common import ORIGINAL_DB, mcp_config  # noqa: E402  (same launch config the backend uses)

# Always test on a fresh temp copy of the ORIGINAL db, so results never depend on the
# working copy's state (e.g. after the Problem 9 run, rent is already paid).
DB = Path(tempfile.mkdtemp()) / "campus_customs_smoke.db"
OUT = HW / "output" / "mcp_smoke.json"

# (vibe-coder prompt, tool, arguments, expected outcome)
CASES = [
    ("Show me every open Campus Customs ticket with all the inventory, pricing, invoice, "
     "lease and cash info linked to it.",
     "get_ticket_context", {}, "ok"),
    ("Pull up ticket 101 and everything it links to so I can see why the tee order is stuck.",
     "get_ticket_context", {"ticket_id": 101}, "ok"),
    ("Check hoodie CC-HOOD-NAVY size M stock for 20 units and who can restock it.",
     "check_stock", {"sku": "CC-HOOD-NAVY", "size": "M", "needed_qty": 20}, "ok"),
    ("Order 12 size M hoodies from Bulldog Print Co for ticket 103.",
     "request_purchase_order", {"vendor_id": 1, "sku": "CC-HOOD-NAVY", "size": "M", "qty": 12,
                                "rationale": "smoke test", "prepared_by": "accountant", "ticket_id": 103}, "refused"),
    ("Queue this month's rent for lease 1 for approval.",
     "request_payment_approval", {"pay_kind": "rent", "ref_id": 1, "rationale": "smoke test",
                                  "prepared_by": "accountant", "ticket_id": 102}, "ok"),
    ("Have the accountant agent approve that rent payment itself.",
     "decide_approval", {"approval_id": 1, "decision": "approved", "decided_by": "accountant"}, "refused"),
    ("As the human owner, approve rent approval 1.",
     "decide_approval", {"approval_id": 1, "decision": "approved", "decided_by": "smoke-test human"}, "ok"),
    ("Queue rent for lease 1 again.",
     "request_payment_approval", {"pay_kind": "rent", "ref_id": 1, "rationale": "smoke test",
                                  "prepared_by": "accountant", "ticket_id": 102}, "refused"),
    ("Give the Yale AI Club their 20 hoodies at $20 each on ticket 103.",
     "resolve_ticket", {"ticket_id": 103, "status": "resolved", "note": "smoke test: below cost",
                        "approved_unit_price": 20.0}, "refused"),
    ("Ship Tauhid's size S tee on ticket 101 and close it.",
     "resolve_ticket", {"ticket_id": 101, "status": "resolved", "note": "smoke test: ship tee",
                        "fulfill_order": True}, "refused"),
    ("Draft a reply to Tauhid on ticket 101 (do not send).",
     "draft_customer_message", {"ticket_id": 101, "subject": "Your tee", "body": "Smoke test draft.",
                                "prepared_by": "customer_service"}, "ok"),
    ("Show me the board.",
     "get_board", {}, "ok"),
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def db_snapshot() -> dict:
    """Direct sqlite3 read (bypassing MCP) used ONLY to verify tool output in this test."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    q = lambda sql, *a: [dict(r) for r in conn.execute(sql, a)]
    snap = {
        "date_today": q("SELECT date_today FROM desk")[0]["date_today"],
        "checking_balance": q("SELECT balance FROM cash_accounts WHERE name='checking'")[0]["balance"],
        "lease_1": q("SELECT monthly_rent, next_due FROM leases WHERE id=1")[0],
        "invoice_501": q("SELECT amount, status FROM invoices WHERE id=501")[0],
        "tee_S_qty": q("SELECT qty FROM inventory WHERE sku='CC-TEE-WHITE' AND size='S'")[0]["qty"],
        "hood_M_qty": q("SELECT qty FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'")[0]["qty"],
        "open_ticket_ids": [r["id"] for r in q("SELECT id FROM tickets WHERE status='open' ORDER BY id")],
    }
    conn.close()
    return snap


def verify(tool: str, args: dict, out: dict | str, before: dict) -> list[str]:
    """Return human-readable checks that tool output matches the database."""
    if isinstance(out, str):
        return [f"refused by server: {out}"]
    checks = []
    if tool == "get_ticket_context":
        assert out["date_today"] == before["date_today"]
        checks.append(f"date_today {out['date_today']} == desk.date_today")
        if "ticket_id" not in args:
            ids = [t["ticket"]["id"] for t in out["tickets"]]
            assert ids == before["open_ticket_ids"]
            checks.append(f"open tickets {ids} == tickets WHERE status='open'")
        for t in out["tickets"]:
            if t["ticket"]["id"] == 101:
                assert t["inventory_requested_size"]["qty"] == before["tee_S_qty"]
                assert t["invoice"]["amount"] == before["invoice_501"]["amount"]
                checks.append(f"ticket 101: tee S qty {before['tee_S_qty']}, invoice 501 ${before['invoice_501']['amount']}")
    elif tool == "check_stock":
        assert out["requested_size"]["qty"] == before["hood_M_qty"]
        v1 = next(v for v in out["vendors"] if v["id"] == 1)
        checks.append(f"hoodie M qty {before['hood_M_qty']} == inventory.qty; shortfall {out['shortfall']}; "
                      f"vendor 1 ships_new_product={v1['ships_new_product']} (open invoices {v1['open_invoice_ids']})")
    elif tool == "request_payment_approval":
        assert out["approval"]["amount"] == before["lease_1"]["monthly_rent"]
        checks.append(f"amount {out['approval']['amount']} == leases.monthly_rent; status pending; no money moved "
                      f"(checking still {out['checking_balance']})")
    elif tool == "decide_approval":
        expected = before["checking_balance"] - out["approval"]["amount"]
        assert out["checking_after"] == expected
        checks.append(f"payment {out['payment']['id']} recorded; checking {before['checking_balance']} -> "
                      f"{out['checking_after']}")
    elif tool == "draft_customer_message":
        checks.append(f"draft {out['draft']['id']} to {out['draft']['recipient']} (tickets.requester); sent={out['sent']}")
    elif tool == "get_board":
        checks.append(f"board: checking {out['checking_balance']}, {len(out['approvals'])} approvals, "
                      f"{len(out['drafts'])} drafts")
    return checks


async def main() -> None:
    shutil.copy2(ORIGINAL_DB, DB)
    original_hash = sha256(DB)
    backup = Path(tempfile.mkdtemp()) / "campus_customs_new.backup.db"
    shutil.copy2(DB, backup)
    results = []
    try:
        async with Client(mcp_config(DB)) as client:
            tools = [t.name for t in await client.list_tools()]
            for prompt, tool, args, expected in CASES:
                before = db_snapshot()
                res = await client.call_tool(tool, args, raise_on_error=False)
                out = res.content[0].text if res.is_error else res.structured_content
                outcome = "refused" if res.is_error else "ok"
                results.append({
                    "vibe_coder_prompt": prompt,
                    "tool": tool,
                    "arguments": args,
                    "expected": expected,
                    "outcome": outcome,
                    "passed": outcome == expected,
                    "verified_against_db": verify(tool, args, out, before),
                    "tool_output": out,
                })
    finally:
        shutil.copy2(backup, DB)
    restored_hash = sha256(DB)

    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "server_config": "backend/common.py mcp_config() (same server as .mcp.json)",
        "transport": "stdio (fastmcp.Client, same launch config as the backend)",
        "database": "temporary copy of data/campus_customs.db (original)",
        "tools_listed_by_server": tools,
        "all_passed": all(r["passed"] for r in results),
        "db_sha256_before": original_hash,
        "db_sha256_after_restore": restored_hash,
        "db_restored_unchanged": original_hash == restored_hash,
        "calls": results,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    for r in results:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['tool']} {r['arguments']} -> {r['outcome']}")
        for c in r["verified_against_db"]:
            print(f"        {c}")
    print(f"all_passed={report['all_passed']}  db_restored_unchanged={report['db_restored_unchanged']}")


if __name__ == "__main__":
    asyncio.run(main())

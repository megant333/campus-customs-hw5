"""Human approval desk (through MCP). The only way money moves. PRACTICE RUN.

    .venv/bin/python backend/approve.py                                   # show the board
    .venv/bin/python backend/approve.py 1 approve --by "Megan Tachev"     # pay (re-checks cash)
    .venv/bin/python backend/approve.py 3 reject --by "Megan Tachev" --reason "not now"
    .venv/bin/python backend/approve.py --db /tmp/scratch.db              # another db file

Calls the campus-customs MCP server's decide_approval / get_board tools. decide_approval
is in no agent's allowlist, refuses agent role names, and refuses the preparer.
Decisions are appended to output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastmcp import Client

from audit import AuditTrail
from common import AUDIT_PATH, WORKING_DB, check_db_path, mcp_config


def client_for(db: Path) -> Client:
    return Client(mcp_config(db))


async def main(args: argparse.Namespace) -> None:
    db = check_db_path(args.db)
    async with client_for(db) as client:
        if args.approval_id is None:
            board = (await client.call_tool("get_board", {})).structured_content
            print(f"Shop date {board['date_today']}  checking ${board['checking_balance']:.2f}  "
                  f"available for new spending ${board['available_for_new_spending']:.2f}\n")
            for a in board["approvals"]:
                what = (f"pay {a['pay_kind']} #{a['ref_id']}" if a["kind"] == "payment"
                        else f"PO vendor {a['vendor_id']}: {a['qty']} x {a['sku']} {a['size']}")
                print(f"[{a['id']}] {a['status']:8} ticket {a['ticket_id']}  {what}  ${a['amount']:.2f}  "
                      f"by {a['prepared_by']}: {a['rationale']}" + (f"  ({a['decision_reason']})" if a["decision_reason"] else ""))
            print("\nTickets:")
            for t in board["tickets"]:
                print(f"  {t['id']} {t['status']:9} {t['type']:15} {t['subject']}")
            print(f"\nDrafts on the board (never sent): {len(board['drafts'])}")
            for d in board["drafts"]:
                print(f"\n--- draft {d['id']} to {d['recipient']} (ticket {d['ticket_id']}): {d['subject']}\n{d['body']}")
            return

        if not (args.decision and args.by):
            raise SystemExit("give a decision (approve/reject) and --by NAME")
        decision = "approved" if args.decision == "approve" else "rejected"
        res = await client.call_tool("decide_approval", {
            "approval_id": args.approval_id, "decision": decision, "decided_by": args.by, "reason": args.reason,
        }, raise_on_error=False)
        audit = AuditTrail(args.audit, f"approve-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}", str(db))
        if res.is_error:
            audit.record("human_decision", agent="human", decided_by=args.by, approval_id=args.approval_id,
                         requested=decision, outcome="refused", error=res.content[0].text)
            raise SystemExit(f"Refused: {res.content[0].text}")
        out = res.structured_content
        audit.record("human_decision", agent="human", decided_by=args.by, approval_id=args.approval_id,
                     requested=decision, outcome=out["approval"]["status"], result=out)
        a = out["approval"]
        print(f"Approval {a['id']}: {a['status']}" + (f" ({a['decision_reason']})" if a["decision_reason"] else ""))
        if out["payment"]:
            print(f"Payment {out['payment']['id']}: ${out['payment']['amount']:.2f} {out['payment']['kind']}")
        print(f"Checking now ${out['checking_after']:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("approval_id", nargs="?", type=int)
    ap.add_argument("decision", nargs="?", choices=["approve", "reject"])
    ap.add_argument("--by", help="name of the person deciding")
    ap.add_argument("--reason")
    ap.add_argument("--db", type=Path, default=WORKING_DB)
    ap.add_argument("--audit", type=Path, default=AUDIT_PATH)
    asyncio.run(main(ap.parse_args()))

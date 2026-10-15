"""Run the Campus Customs team over the ticket board (PRACTICE RUN - nothing leaves the board).

    .venv/bin/python backend/run_team.py               # FULL RUN: reset db to original, work all open tickets
    .venv/bin/python backend/run_team.py --continue    # after human approvals: work open + pending tickets
    .venv/bin/python backend/run_team.py --ticket 103  # one ticket, no reset
    .venv/bin/python backend/run_team.py --db /tmp/scratch.db --audit /tmp/audit.json   # dry run

Tickets run one at a time, in id order, because they compete for the same cash.
Every agent-loop step is appended to output/audit_trail.json (never wiped).
The run summary goes to output/team_run.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from audit import AuditTrail
from common import AUDIT_PATH, HW, MODEL_NAME, WORKING_DB, check_db_path
from reset_db import reset
from team import build_team, work_ticket

OUT = HW / "output" / "team_run.json"


async def main(args: argparse.Namespace) -> None:
    db = check_db_path(args.db)
    mode = "ticket" if args.ticket is not None else "continue" if args.cont else "full"
    reset_info = reset(db) if mode == "full" and not args.no_reset else None

    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    audit = AuditTrail(args.audit, run_id, str(db))
    team = build_team(db)
    runs = []
    async with team.mcp:  # one MCP server process for the whole team
        statuses = ["open", "pending"] if mode == "continue" else ["open"]
        board = await team.mcp.direct_call_tool("get_ticket_context", {"statuses": statuses})
        audit.shop_date = board["date_today"]
        ids = [args.ticket] if mode == "ticket" else [t["ticket"]["id"] for t in board["tickets"]]
        audit.record("run_start", mode=mode, model=MODEL_NAME, tickets=ids, reset=reset_info)
        try:
            for tid in ids:
                try:
                    run = await work_ticket(team, tid, audit)
                except Exception as exc:  # one bad ticket must not stop the board (logged in the audit)
                    print(f"\n=== Ticket {tid} FAILED: {type(exc).__name__}: {str(exc)[:200]}")
                    runs.append({"ticket_id": tid, "error": f"{type(exc).__name__}: {exc}"[:2000],
                                 "usage": {"requests": 0, "input_tokens": 0, "output_tokens": 0}})
                    continue
                runs.append(run)
                d = run["decision"]
                path = " | ".join(f"{x['from']}->{x['to']}" for x in run["delegations"])
                print(f"\n=== Ticket {tid} ({d['ticket_type']}) -> {d['status']}")
                print(f"    delegations: {path}")
                print(f"    call: {d['final_call']}")
                if d["approval_ids"]:
                    print(f"    linked approvals: {d['approval_ids']}  needs human: {d['needs_human'] or 'nothing'}")
                print(f"    usage: {run['usage']}")
        finally:
            total = {k: sum(r["usage"][k] for r in runs) for k in ("requests", "input_tokens", "output_tokens")}
            audit.record("run_end", mode=mode, completed=[r["ticket_id"] for r in runs if "error" not in r],
                         failed=[r["ticket_id"] for r in runs if "error" in r], total_usage=total)

    args.out.parent.mkdir(exist_ok=True)
    args.out.write_text(json.dumps({
        "run_id": run_id, "run_at": datetime.now().isoformat(timespec="seconds"), "mode": mode,
        "model": MODEL_NAME, "database": str(db), "reset": reset_info, "total_usage": total, "tickets": runs,
    }, indent=2) + "\n")
    print(f"\nTotal usage: {total}\nRun summary: {args.out.resolve()}\nAudit trail: {args.audit.resolve()}")
    print("Next: review the board and decide approvals with backend/approve.py, then --continue.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", type=int)
    ap.add_argument("--continue", dest="cont", action="store_true")
    ap.add_argument("--no-reset", action="store_true", help="skip the automatic reset on a full run")
    ap.add_argument("--db", type=Path, default=WORKING_DB)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--audit", type=Path, default=AUDIT_PATH)
    asyncio.run(main(ap.parse_args()))

"""FastAPI backend for the Campus Customs desk dashboard (PRACTICE RUN).

Start from backend/:   ../.venv/bin/uvicorn main:app --reload --port 8000
                       -> http://localhost:8000   (interactive docs at /docs)

Routes
  GET  /api/health                     liveness + which database/model the server uses
  GET  /api/tickets                    the tickets with status (open / pending / resolved / declined)
  POST /api/tickets/{id}/run           run the agent team on one ticket (one run at a time)
  GET  /api/events?since=&limit=       recent agent events from output/audit_trail.json
  GET  /api/approvals                  approvals (pending first, payment-priority order)
  POST /api/approvals/{id}/decision    HUMAN approves/rejects a payment or purchase order
  GET  /api/cash                       current checking balance from cash_accounts
  POST /api/reset                      reset the working db to the original values

Every shop fact goes through the campus-customs MCP server (one shared connection).
The routes never touch the database directly. The only file the API reads itself is
the audit trail, and reset copies the original db file through backend/reset_db.py.

Env overrides (for dry runs only): CAMPUS_CUSTOMS_DB, CAMPUS_CUSTOMS_AUDIT.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_ai.exceptions import ToolFailed

from audit import AuditTrail
from common import AGENT_ROLES_FOR_API, AUDIT_PATH, MODEL_NAME, WORKING_DB, check_db_path
from reset_db import reset
from team import Team, build_team, work_ticket

DB_PATH = check_db_path(Path(os.environ.get("CAMPUS_CUSTOMS_DB", WORKING_DB)))
AUDIT_FILE = Path(os.environ.get("CAMPUS_CUSTOMS_AUDIT", AUDIT_PATH))

state: dict[str, Any] = {}
run_lock = asyncio.Lock()  # one agent run (or reset) at a time: tickets share the same cash


@asynccontextmanager
async def lifespan(app: FastAPI):
    team = build_team(DB_PATH)
    async with team.mcp:  # one MCP server process for the whole API lifetime
        state["team"] = team
        yield
    state.clear()


app = FastAPI(title="Campus Customs Desk API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,  # the Vite dev server (frontend/) runs on :5173 and calls this API directly
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",  # any other local port (vite picks the next free one)
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _team() -> Team:
    return state["team"]


async def mcp(tool: str, args: dict[str, Any] | None = None) -> Any:
    """Call a campus-customs MCP tool; turn a refusal into a 400 with the server's reason."""
    try:
        return await _team().mcp.direct_call_tool(tool, args or {})
    except ToolFailed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _audit(prefix: str) -> AuditTrail:
    return AuditTrail(AUDIT_FILE, f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}", str(DB_PATH))


# ------------------------------------------------------------------ routes

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "database": str(DB_PATH), "model": MODEL_NAME, "practice_run": True,
            "run_in_progress": run_lock.locked()}


@app.get("/api/tickets")
async def tickets() -> dict[str, Any]:
    """Every ticket with its status; `open` is true until it is resolved or declined."""
    board = await mcp("get_board")
    return {
        "date_today": board["date_today"],
        "tickets": [
            {**t, "is_open": t["status"] not in ("resolved", "declined"),
             "approvals": [a for a in board["approvals"] if a["ticket_id"] == t["id"]],
             "drafts": [d for d in board["drafts"] if d["ticket_id"] == t["id"]]}
            for t in board["tickets"]
        ],
    }


@app.post("/api/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int) -> dict[str, Any]:
    """Run the five-agent team on one ticket. Returns the boss's decision, delegations and usage."""
    if run_lock.locked():
        raise HTTPException(status_code=409, detail="A run or reset is already in progress")
    async with run_lock:
        context = await mcp("get_ticket_context", {"ticket_id": ticket_id})
        status = context["tickets"][0]["ticket"]["status"]
        if status in ("resolved", "declined"):
            raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is already {status}")
        audit = _audit("api-run")
        audit.shop_date = context["date_today"]
        audit.record("run_start", mode="api", model=MODEL_NAME, tickets=[ticket_id])
        try:
            result = await work_ticket(_team(), ticket_id, audit)
        except Exception as exc:
            audit.record("run_end", mode="api", completed=[], failed=[ticket_id], error=str(exc)[:2000])
            raise HTTPException(status_code=502, detail=f"Team run failed: {type(exc).__name__}: {exc}") from exc
        audit.record("run_end", mode="api", completed=[ticket_id], failed=[], total_usage=result["usage"])
        return result


def _event_view(index: int, r: dict[str, Any]) -> dict[str, Any] | None:
    """Turn one audit record into a dashboard event: who, what they said, which tools."""
    base = {"id": index, "run_id": r.get("run_id"), "logged_at": r.get("logged_at"),
            "ticket_id": r.get("ticket_id"), "agent": r.get("agent"), "chain": r.get("chain"),
            "event": r["event"]}
    match r["event"]:
        case "agent_start":
            return {**base, "said": r.get("request")}
        case "model_response":
            calls = [c for c in r.get("tool_calls", []) if c["tool"] != "final_result"]
            tokens = {"in": r.get("input_tokens"), "out": r.get("output_tokens")}
            if not calls and not r.get("text"):
                # The final-output call: no tools to show (agent_end carries the answer), but its
                # tokens are real and must reach the token sidebar.
                return {**base, "final_output": True, "tools": [], "tokens": tokens}
            return {**base, "said": r.get("text"), "tools": [c["tool"] for c in calls],
                    "tool_args": [c["args"] for c in calls],
                    "tokens": {"in": r.get("input_tokens"), "out": r.get("output_tokens")}}
        case "tool_results":
            return {**base, "results": [{"tool": x["tool"], "outcome": x["outcome"], "content": x["content"][:500]}
                                        for x in r.get("results", []) if x["tool"] != "final_result"]} \
                if any(x["tool"] != "final_result" for x in r.get("results", [])) else None
        case "agent_end":
            out = r.get("output") or {}
            said = out.get("final_call") or out.get("summary") or out.get("body")
            return {**base, "said": said, "output": out,
                    "tokens": {"in": r.get("input_tokens"), "out": r.get("output_tokens")}}
        case "human_decision":
            return {**base, "agent": "human", "said": f"{r.get('decided_by')}: {r.get('requested')} approval "
                                                      f"{r.get('approval_id')} -> {r.get('outcome')}"}
        case "error" | "run_start" | "run_end" | "reset":
            return {**base, **{k: r[k] for k in ("error", "mode", "tickets", "completed", "failed",
                                                 "total_usage", "result") if k in r}}
    return None


@app.get("/api/events")
async def events(since: int = 0, limit: int = 100, ticket_id: int | None = None) -> dict[str, Any]:
    """Recent agent events (newest last). Poll with ?since=<next_since> to get only new ones."""
    limit = max(1, min(limit, 500))
    try:
        records = json.loads(AUDIT_FILE.read_text()) if AUDIT_FILE.exists() else []
    except json.JSONDecodeError:
        records = []  # mid-write or damaged; next poll will succeed
    views = [v for i, r in enumerate(records) if i >= since and (v := _event_view(i, r))
             and (ticket_id is None or v.get("ticket_id") in (ticket_id, None))]
    return {"events": views[-limit:], "next_since": len(records), "run_in_progress": run_lock.locked()}


@app.get("/api/approvals")
async def approvals() -> dict[str, Any]:
    board = await mcp("get_board")
    return {"approvals": board["approvals"], "checking_balance": board["checking_balance"],
            "available_for_new_spending": board["available_for_new_spending"]}


class Decision(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(min_length=2, max_length=60, description="the human making the call")
    confirm: bool = Field(description="must be true: the human explicitly confirms this decision")
    reason: str | None = Field(None, max_length=500)


@app.post("/api/approvals/{approval_id}/decision")
async def decide(approval_id: int, body: Decision) -> dict[str, Any]:
    """HUMAN ONLY. Approving pays (re-checking cash); the server auto-rejects if cash is short."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true to record a human decision")
    if body.decided_by.strip().lower().replace(" ", "_") in AGENT_ROLES_FOR_API:
        raise HTTPException(status_code=403, detail="decided_by must be a human, not an agent role")
    if run_lock.locked():
        raise HTTPException(status_code=409, detail="Wait for the current agent run to finish")
    audit = _audit("api-approve")
    try:
        result = await _team().mcp.direct_call_tool("decide_approval", {
            "approval_id": approval_id, "decision": body.decision,
            "decided_by": body.decided_by.strip(), "reason": body.reason,
        })
    except ToolFailed as exc:
        audit.record("human_decision", agent="human", decided_by=body.decided_by, approval_id=approval_id,
                     requested=body.decision, outcome="refused", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit.record("human_decision", agent="human", decided_by=body.decided_by, approval_id=approval_id,
                 requested=body.decision, outcome=result["approval"]["status"], result=result)
    return result


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    fin = await mcp("get_finances")
    return {"date_today": fin["date_today"], "checking_balance": fin["checking_balance"],
            "available_for_new_spending": fin["available_for_new_spending"],
            "committed_outflows": fin["committed_outflows"]}


class ResetRequest(BaseModel):
    confirm: bool = Field(description="must be true: wipes the working copy back to the original")


@app.post("/api/reset")
async def reset_db(body: ResetRequest) -> dict[str, Any]:
    """Copy the original database over the working copy (previous copy backed up first)."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true to reset")
    if run_lock.locked():
        raise HTTPException(status_code=409, detail="A run is in progress; reset after it finishes")
    async with run_lock:
        info = reset(DB_PATH)
        _audit("api-reset").record("reset", agent="human", result=info)
        return info

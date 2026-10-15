"""Append-only audit trail for the agent team: output/audit_trail.json.

One JSON array that only ever grows: every run adds records, and nothing is wiped.
Each agent-loop step is written the moment it happens (crash-safe atomic rewrite), with:
  run_id, seq, logged_at (wall clock), shop_date (desk.date_today), database,
  ticket_id, agent, chain (who delegated to whom), step, event, and the event's details.

Events
  run_start / run_end      one per run_team invocation (mode, tickets, totals)
  agent_start              agent began; the request it received
  model_response           one per model call: tool calls (+args), text, tokens, finish reason
  tool_results             results the agent got back (MCP + delegate), ok/failed, truncated
  agent_end                the agent's typed output and its token usage
  error                    any exception, before it propagates

API keys never reach these records: only messages, tool args and tool results are logged.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_CONTENT_CHARS = 2000  # tool results are truncated in the log; the db holds the full state


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= MAX_CONTENT_CHARS else text[:MAX_CONTENT_CHARS] + f"... [+{len(text) - MAX_CONTENT_CHARS} chars]"


class AuditTrail:
    def __init__(self, path: Path, run_id: str, database: str, shop_date: str | None = None):
        self.path = path
        self.run_id = run_id
        self.database = database
        self.shop_date = shop_date
        self.seq = 0

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            # Never destroy history: park the unreadable file and start a fresh array.
            self.path.rename(self.path.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
            return []
        return data if isinstance(data, list) else [data]

    def record(self, event: str, **fields: Any) -> None:
        self.seq += 1
        entry = {
            "run_id": self.run_id,
            "seq": self.seq,
            "logged_at": datetime.now().isoformat(timespec="milliseconds"),
            "shop_date": self.shop_date,
            "database": self.database,
            "event": event,
            **fields,
        }
        records = self._load()
        records.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(records, f, indent=1, default=str)
            f.write("\n")
        os.replace(tmp, self.path)


def response_details(response) -> dict[str, Any]:
    """Summarize one ModelResponse for the audit trail."""
    calls, text = [], []
    for part in response.parts:
        kind = getattr(part, "part_kind", "")
        if kind == "tool-call":
            calls.append({"tool": part.tool_name, "call_id": part.tool_call_id, "args": part.args_as_dict()})
        elif kind == "text" and part.content.strip():
            text.append(part.content)
    usage = response.usage
    return {
        "model": response.model_name,
        "tool_calls": calls,
        "text": _clip("\n".join(text)) if text else None,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "finish_reason": response.finish_reason,
    }


def request_details(request) -> list[dict[str, Any]]:
    """Tool results / retry prompts inside a ModelRequest (what the agent got back)."""
    out = []
    for part in request.parts:
        kind = getattr(part, "part_kind", "")
        if kind == "tool-return":
            out.append({"tool": part.tool_name, "call_id": part.tool_call_id,
                        "outcome": getattr(part, "outcome", "success"), "content": _clip(part.content)})
        elif kind == "retry-prompt":
            out.append({"tool": part.tool_name, "call_id": part.tool_call_id,
                        "outcome": "retry", "content": _clip(part.content)})
    return out

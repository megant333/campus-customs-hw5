"""Assemble the five-agent team and work tickets.

    work_ticket(team, 101, audit)  ->  {"decision": ..., "delegations": [...], "usage": {...}}

All shop facts come through the MCP server. Importable by a future web API as well as
by run_team.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.mcp import MCPToolset

import accountant
import boss
import customer_service
import facilities
import inventory
from audit import AuditTrail
from common import WORKING_DB, TeamDeps, build_mcp_toolset, build_model, run_logged, tools_called

MEMBERS = (boss, inventory, accountant, facilities, customer_service)
# Per ticket, shared by every agent in the delegation tree: caps runaway loops and cost.
LIMITS = UsageLimits(request_limit=30, tool_calls_limit=40, total_tokens_limit=80_000)


@dataclass
class Team:
    agents: dict[str, Agent]
    mcp: MCPToolset


def build_team(db_path=WORKING_DB) -> Team:
    model = build_model()
    mcp = build_mcp_toolset(db_path)
    return Team(agents={m.ROLE: m.build(model, mcp) for m in MEMBERS}, mcp=mcp)


def compact_ticket(ctx: dict[str, Any]) -> dict[str, Any]:
    """The ticket row plus its board state (approvals, drafts), trimmed to what agents use."""
    ticket = dict(ctx["ticket"])
    ticket["approvals"] = [
        {k: a[k] for k in ("id", "kind", "pay_kind", "ref_id", "sku", "size", "qty", "amount", "status",
                           "decision_reason", "expected_date")}
        for a in ctx["approvals"]
    ]
    ticket["draft_ids"] = [d["id"] for d in ctx["drafts"]]
    return ticket


async def work_ticket(team: Team, ticket_id: int, audit: AuditTrail) -> dict[str, Any]:
    """Run the boss on one ticket. Call inside `async with team.mcp:`."""
    context = await team.mcp.direct_call_tool("get_ticket_context", {"ticket_id": ticket_id})
    audit.shop_date = context["date_today"]
    deps = TeamDeps(agents=team.agents, ticket=compact_ticket(context["tickets"][0]), audit=audit, chain=("boss",))
    result = await run_logged(team.agents["boss"], "boss", f"Work ticket {ticket_id}.", deps, usage_limits=LIMITS)
    usage = result.usage
    return {
        "ticket_id": ticket_id,
        "decision": result.output.model_dump(),
        "boss_mcp_tools_used": tools_called(result.new_messages()),
        "delegations": deps.trace,
        "usage": {"requests": usage.requests, "input_tokens": usage.input_tokens,
                  "output_tokens": usage.output_tokens},
    }

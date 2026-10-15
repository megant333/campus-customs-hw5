"""Boss: reads each ticket, routes work to teammates, and makes the final call."""

from __future__ import annotations

import json

from pydantic_ai import Agent, ModelRetry, RunContext

from common import TeamDeps, make_agent, settings, successful_returns
from models import TicketDecision

ROLE = "boss"
# The ticket row is injected into instructions and specialists fetch the linked rows they
# need, so the boss only needs the write tool. Dropping get_ticket_context saved ~1.5k tokens
# per call it was making, re-sent on every later boss request.
MCP_TOOLS = {"resolve_ticket"}
SETTINGS = settings(effort="medium", max_tokens=6000)  # routing + final judgment


def build(model, mcp) -> Agent[TeamDeps, TicketDecision]:
    agent = make_agent(ROLE, model, mcp, MCP_TOOLS, TicketDecision, SETTINGS,
                       once_tools=frozenset({"resolve_ticket"}))

    @agent.output_validator
    def consistent(ctx: RunContext[TeamDeps], out: TicketDecision) -> TicketDecision:
        if out.ticket_id != ctx.deps.ticket["id"]:
            raise ModelRetry(f"ticket_id must be {ctx.deps.ticket['id']}")
        writes = successful_returns(ctx.messages, "resolve_ticket")
        if not writes:
            raise ModelRetry("call resolve_ticket (once) before returning your decision")
        last = writes[-1] if isinstance(writes[-1], dict) else json.loads(writes[-1])
        written = last["ticket_after"]["status"]
        if out.status != written:
            raise ModelRetry(f"status must be '{written}', the status you wrote with resolve_ticket")
        # Pending approvals are enforced by resolve_ticket itself; here, outstanding human work.
        if out.status == "resolved" and out.needs_human:
            raise ModelRetry("status cannot be 'resolved' while needs_human lists outstanding actions")
        return out

    return agent

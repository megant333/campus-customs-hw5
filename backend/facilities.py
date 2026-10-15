"""Facilities: the shop space side - lease, landlord, and rent notices."""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext

from common import TeamDeps, make_agent, settings
from models import FacilitiesReport

ROLE = "facilities"
MCP_TOOLS = {"get_lease_status"}
SETTINGS = settings(effort="low", max_tokens=4000)


def build(model, mcp) -> Agent[TeamDeps, FacilitiesReport]:
    agent = make_agent(ROLE, model, mcp, MCP_TOOLS, FacilitiesReport, SETTINGS)

    @agent.output_validator
    def consistent(ctx: RunContext[TeamDeps], out: FacilitiesReport) -> FacilitiesReport:
        if out.recommendation == "pay" and not out.notice_matches_lease:
            raise ModelRetry("never recommend 'pay' when the notice does not match the lease")
        if out.recommendation == "pay" and out.period_status in ("pending", "approved"):
            raise ModelRetry(f"this period is already {out.period_status}; recommend 'already_queued' or 'already_paid'")
        return out

    return agent

"""Inventory: stock by sku/size, shortfalls, and which vendor can restock."""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext

from common import TeamDeps, make_agent, settings
from models import InventoryReport

ROLE = "inventory"
MCP_TOOLS = {"check_stock"}  # one call returns stock, shortfall, vendors, ETAs, covering invoices
SETTINGS = settings(effort="low", max_tokens=4000)


def build(model, mcp) -> Agent[TeamDeps, InventoryReport]:
    agent = make_agent(ROLE, model, mcp, MCP_TOOLS, InventoryReport, SETTINGS)

    @agent.output_validator
    def consistent(ctx: RunContext[TeamDeps], out: InventoryReport) -> InventoryReport:
        all_covered = all((line.shortfall or 0) == 0 for line in out.lines)
        if out.can_fulfil_now != all_covered:
            raise ModelRetry("can_fulfil_now must be true exactly when every shortfall is 0")
        return out

    return agent

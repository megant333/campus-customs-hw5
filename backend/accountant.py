"""Accountant: cash, invoices, margins; prepares payments and purchase orders for approval."""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext

from common import TeamDeps, make_agent, settings
from models import FinanceReport

ROLE = "accountant"
MCP_TOOLS = {"get_finances", "quote_margin", "request_payment_approval", "request_purchase_order"}
SETTINGS = settings(effort="low", max_tokens=4000)


def build(model, mcp) -> Agent[TeamDeps, FinanceReport]:
    agent = make_agent(ROLE, model, mcp, MCP_TOOLS, FinanceReport, SETTINGS)

    @agent.output_validator
    def consistent(ctx: RunContext[TeamDeps], out: FinanceReport) -> FinanceReport:
        if out.margin_pct is not None and out.recommended_unit_price is not None and out.margin_pct < 50:
            raise ModelRetry("shop rule: recommended price must keep margin_pct >= 50; raise it")
        return out

    return agent

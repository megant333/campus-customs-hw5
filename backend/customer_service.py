"""Customer service: drafts replies to requesters (never sends them)."""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext

from common import TeamDeps, make_agent, settings
from models import CustomerDraft

ROLE = "customer_service"
MCP_TOOLS = {"draft_customer_message"}
SETTINGS = settings(effort="none", max_tokens=1500)  # drafting from given facts needs no reasoning
MAX_WORDS = 130


def build(model, mcp) -> Agent[TeamDeps, CustomerDraft]:
    agent = make_agent(ROLE, model, mcp, MCP_TOOLS, CustomerDraft, SETTINGS,
                       once_tools=frozenset({"draft_customer_message"}))

    @agent.output_validator
    def consistent(ctx: RunContext[TeamDeps], out: CustomerDraft) -> CustomerDraft:
        if len(out.body.split()) > MAX_WORDS:
            raise ModelRetry(f"draft is over {MAX_WORDS} words; return a shortened body (the saved draft stands)")
        return out

    return agent

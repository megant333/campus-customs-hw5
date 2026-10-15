"""Typed data for the Campus Customs agent team (PydanticAI output types).

Each specialist returns its report model to whoever delegated to it; the boss
returns a TicketDecision. Every number, ID, and date in these models must be
copied from an MCP tool result or a teammate's report, never estimated.
Field descriptions are sent to the model as the output schema, so they are
kept short to save tokens.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["boss", "inventory", "accountant", "facilities", "customer_service"]
TicketStatus = Literal["open", "pending", "resolved", "declined"]


class StockLine(BaseModel):
    sku: str
    size: str
    on_hand: int
    needed: int | None = None
    shortfall: int | None = None
    location: str | None = None


class InventoryReport(BaseModel):
    """Stock by sku/size, shortfall, and how it gets restocked."""

    ticket_id: int
    lines: list[StockLine]
    can_fulfil_now: bool = Field(description="true only if every shortfall is 0")
    covering_invoice_id: int | None = Field(None, description="open invoice already covering the restock")
    restock_blocked_by_invoice_ids: list[int] = Field(default_factory=list, description="vendor won't ship until paid")
    restock_vendor_id: int | None = None
    restock_vendor_name: str | None = None
    restock_qty: int | None = None
    earliest_restock_date: str | None = None
    restock_cost_estimate: float | None = None
    alternatives: list[str] = Field(default_factory=list, description="in-stock options, exact qty")
    approval_ids: list[int] = Field(default_factory=list, description="approvals created via delegation")
    summary: str


class FinanceReport(BaseModel):
    """Cash, invoices, margins, and approvals prepared for a human."""

    ticket_id: int
    checking_balance: float
    checking_after_all_pending: float | None = None
    recommended_unit_price: float | None = None
    margin_per_unit: float | None = None
    margin_pct: float | None = None
    margin_total: float | None = None
    revenue_total: float | None = Field(None, description="quote_margin revenue_total for the full qty")
    approval_ids: list[int] = Field(default_factory=list, description="approvals rows created")
    risks: list[str] = Field(default_factory=list)
    summary: str


class FacilitiesReport(BaseModel):
    """Lease and rent side of the shop space."""

    ticket_id: int
    lease_id: int | None
    landlord: str | None = None
    monthly_rent: float | None = None
    next_due: str | None = None
    days_until_due: int | None = None
    period_status: Literal["unpaid", "pending", "approved"] | None = None
    notice_matches_lease: bool = Field(description="requester == leases.landlord, no contradictions")
    recommendation: Literal["pay", "already_queued", "already_paid", "decline", "investigate"]
    approval_ids: list[int] = Field(default_factory=list, description="approvals created via delegation")
    summary: str


class CustomerDraft(BaseModel):
    """A reply saved (not sent) with draft_customer_message."""

    ticket_id: int
    draft_id: int = Field(description="customer_messages.id from the tool")
    recipient: str
    subject: str
    body: str


class TicketDecision(BaseModel):
    """The boss's final call on one ticket."""

    ticket_id: int
    ticket_type: str
    assigned_to: list[Role]
    final_call: str = Field(description="what the shop will do, 1-3 sentences")
    status: TicketStatus = Field(description="status written with resolve_ticket")
    approved_unit_price: float | None = None
    approval_ids: list[int] = Field(default_factory=list, description="approvals linked to this ticket")
    customer_draft_id: int | None = None
    needs_human: list[str] = Field(default_factory=list, description="outstanding human actions only")


Report = InventoryReport | FinanceReport | FacilitiesReport | CustomerDraft | TicketDecision

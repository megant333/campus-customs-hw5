// Shapes returned by the FastAPI routes in backend/main.py.

export type TicketStatus = "open" | "pending" | "resolved" | "declined";
export type AgentId = "boss" | "inventory" | "accountant" | "facilities" | "customer_service";
export type NodeId = AgentId | "mcp" | "human";

export interface Approval {
  id: number;
  kind: "payment" | "purchase_order";
  ticket_id: number | null;
  pay_kind: "rent" | "invoice" | null;
  ref_id: number | null;
  vendor_id: number | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  amount: number;
  amount_basis: string;
  rationale: string;
  prepared_by: string;
  status: "pending" | "approved" | "rejected";
  decided_by: string | null;
  decision_reason: string | null;
  expected_date: string | null;
}

export interface Draft {
  id: number;
  ticket_id: number;
  recipient: string;
  subject: string;
  body: string;
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: TicketStatus;
  notes: string | null;
  is_open: boolean;
  approvals: Approval[];
  drafts: Draft[];
}

export interface TicketsResponse {
  date_today: string;
  tickets: Ticket[];
}

export interface Cash {
  date_today: string;
  checking_balance: number;
  available_for_new_spending: number;
}

export interface AgentEvent {
  id: number;
  run_id: string;
  logged_at: string;
  ticket_id: number | null;
  agent: AgentId | "human" | null;
  chain: AgentId[] | null;
  event: "agent_start" | "model_response" | "tool_results" | "agent_end" | "human_decision" | "error"
    | "run_start" | "run_end" | "reset";
  said?: string | null;
  tools?: string[];
  tool_args?: Record<string, unknown>[];
  results?: { tool: string; outcome: string; content: string }[];
  output?: Record<string, unknown>;
  tokens?: { in: number | null; out: number | null };
  final_output?: boolean;
  error?: string;
  tickets?: number[];
}

export interface EventsResponse {
  events: AgentEvent[];
  next_since: number;
  run_in_progress: boolean;
}

export interface RunResult {
  ticket_id: number;
  decision: {
    status: TicketStatus;
    final_call: string;
    approval_ids: number[];
    needs_human: string[];
  };
  usage: { requests: number; input_tokens: number; output_tokens: number };
}

import type { AgentEvent, AgentId, NodeId } from "./types";

export const AGENTS: { id: AgentId; name: string; role: string; color: string; glyph: string }[] = [
  { id: "boss", name: "Boss", role: "Routes tickets · final call", color: "#d9a441", glyph: "★" },
  { id: "inventory", name: "Inventory", role: "Stock · shortfalls · vendors", color: "#5fa486", glyph: "▦" },
  { id: "accountant", name: "Accountant", role: "Cash · margins · approvals", color: "#5b86e5", glyph: "$" },
  { id: "facilities", name: "Facilities", role: "Lease · rent notices", color: "#d97a5b", glyph: "⌂" },
  { id: "customer_service", name: "Customer Service", role: "Drafts replies (never sent)", color: "#a37ad6", glyph: "✉" },
];

export const NODE_COLOR: Record<NodeId, string> = {
  ...Object.fromEntries(AGENTS.map((a) => [a.id, a.color])),
  mcp: "#6b6f7a",
  human: "#e0708c",
} as Record<NodeId, string>;

export const agentName = (id: string | null | undefined) =>
  AGENTS.find((a) => a.id === id)?.name ?? (id === "human" ? "Human" : id ?? "System");

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

/** Events belonging to the most recent run that touched this ticket. */
export function latestRunEvents(events: AgentEvent[], ticketId: number): AgentEvent[] {
  const last = [...events].reverse().find((e) => e.ticket_id === ticketId && e.event === "agent_start");
  if (!last) return [];
  return events.filter((e) => e.run_id === last.run_id && (e.ticket_id === ticketId || e.ticket_id === null));
}

/** Every event for this ticket since the board was last reset (all runs: first pass + follow-ups). */
export function ticketEvents(events: AgentEvent[], ticketId: number): AgentEvent[] {
  let start = 0;
  events.forEach((e, i) => {
    if (e.event === "reset" || (e.event === "run_start" && (e as { mode?: string }).mode === "full")) start = i + 1;
  });
  return events.slice(start).filter((e) => e.ticket_id === ticketId);
}

/** Human-readable line for one event in the live feed. */
export function describe(e: AgentEvent): string {
  switch (e.event) {
    case "agent_start":
      return e.chain && e.chain.length > 1 ? `picked up a request from ${agentName(e.chain[e.chain.length - 2])}` : "started the ticket";
    case "model_response": {
      if (e.said) return e.said;
      const targets = (e.tools ?? []).map((t, i) => (t === "delegate" ? agentName(String(e.tool_args?.[i]?.to)) : null)).filter(Boolean);
      const tools = (e.tools ?? []).filter((t) => t !== "delegate");
      const parts = [targets.length ? `handing off to ${targets.join(" & ")}` : "", tools.length ? `calling ${tools.join(", ")}` : ""];
      return parts.filter(Boolean).join(" · ") || "thinking";
    }
    case "tool_results":
      return (e.results ?? []).map((r) => `${r.tool} → ${r.outcome}`).join(" · ");
    case "agent_end":
      return e.said ?? "finished";
    case "error":
      return e.error ?? "error";
    default:
      return e.said ?? e.event;
  }
}

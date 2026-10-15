import type { Approval, Cash, EventsResponse, RunResult, TicketsResponse } from "./types";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
  return body as T;
}

export const api = {
  tickets: () => call<TicketsResponse>("/api/tickets"),
  cash: () => call<Cash>("/api/cash"),
  approvals: () => call<{ approvals: Approval[] }>("/api/approvals"),
  events: (since: number, limit = 500) => call<EventsResponse>(`/api/events?since=${since}&limit=${limit}`),
  run: (ticketId: number) => call<RunResult>(`/api/tickets/${ticketId}/run`, { method: "POST" }),
  decide: (approvalId: number, decision: "approved" | "rejected", decidedBy: string) =>
    call<{ approval: Approval; checking_after: number }>(`/api/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, decided_by: decidedBy, confirm: true }),
    }),
  reset: () => call<Record<string, unknown>>("/api/reset", { method: "POST", body: JSON.stringify({ confirm: true }) }),
};

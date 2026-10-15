import { useState } from "react";
import { agentName, money } from "../agents";
import type { Approval } from "../types";

// Human approval desk: nothing is paid until a named person clicks Approve and confirms.

function what(a: Approval) {
  if (a.kind === "payment") return a.pay_kind === "rent" ? `Pay rent · lease ${a.ref_id}` : `Pay invoice ${a.ref_id}`;
  return `Purchase order · ${a.qty} × ${a.sku} ${a.size}`;
}

export default function Approvals({ approvals, selected, busy, onDecide }: {
  approvals: Approval[]; selected: number | null; busy: boolean;
  onDecide: (a: Approval, decision: "approved" | "rejected", by: string) => Promise<void>;
}) {
  const [name, setName] = useState(() => localStorage.getItem("approver") ?? "");
  const [working, setWorking] = useState<number | null>(null);
  const pending = approvals.filter((a) => a.status === "pending")
    .sort((x, y) => Number(y.ticket_id === selected) - Number(x.ticket_id === selected));
  const decided = approvals.filter((a) => a.status !== "pending").slice(-4).reverse();

  async function decide(a: Approval, decision: "approved" | "rejected") {
    const by = name.trim();
    if (by.length < 2) { alert("Type your name first - approvals are recorded with the person who made them."); return; }
    const verb = decision === "approved" ? "APPROVE and pay" : "REJECT";
    if (!confirm(`${verb} ${money(a.amount)}?\n${what(a)} (ticket ${a.ticket_id})\n\nRecorded as decided by ${by}.`)) return;
    localStorage.setItem("approver", by);
    setWorking(a.id);
    try { await onDecide(a, decision, by); } finally { setWorking(null); }
  }

  return (
    <section className={`approvals glass ${pending.length ? "attention" : ""}`}>
      <div className="panel-title">
        <span>Human approvals</span>
        {pending.length > 0 && <span className="chip attention">{pending.length} waiting for you</span>}
      </div>
      <label className="approver">
        <span>Approving as</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
      </label>
      {pending.length === 0 && <div className="empty">No payments or purchase orders are waiting.</div>}
      {pending.map((a) => (
        <div key={a.id} className={`approval ${a.ticket_id === selected ? "mine" : ""}`}>
          <div className="approval-main">
            <div className="approval-what">{what(a)}</div>
            <div className="approval-amt">{money(a.amount)}</div>
          </div>
          <div className="approval-why">Ticket {a.ticket_id} · prepared by {agentName(a.prepared_by)} · {a.rationale}</div>
          <div className="approval-basis">{a.amount_basis}</div>
          <div className="approval-actions">
            <button className="btn primary" disabled={busy || working !== null} onClick={() => decide(a, "approved")}>
              {working === a.id ? "Recording…" : "Approve"}
            </button>
            <button className="btn ghost" disabled={busy || working !== null} onClick={() => decide(a, "rejected")}>Reject</button>
          </div>
        </div>
      ))}
      {decided.length > 0 && (
        <div className="decided">
          {decided.map((a) => (
            <div key={a.id} className="decided-row">
              <span className={`chip status-${a.status === "approved" ? "resolved" : "declined"}`}>{a.status}</span>
              <span>{what(a)} · {money(a.amount)}</span>
              <span className="muted">{a.decided_by}{a.decision_reason ? ` · ${a.decision_reason}` : ""}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

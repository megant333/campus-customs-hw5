import type { Ticket } from "../types";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

export default function TicketBoard({ tickets, selected, running, onSelect }:
  { tickets: Ticket[]; selected: number | null; running: number | null; onSelect: (id: number) => void }) {
  return (
    <section className="board">
      {tickets.map((t) => {
        const pending = t.approvals.filter((a) => a.status === "pending").length;
        return (
          <button key={t.id} className={`ticket glass ${selected === t.id ? "selected" : ""}`} onClick={() => onSelect(t.id)}>
            <div className="ticket-top">
              <span className="ticket-id">#{t.id}</span>
              <span className={`chip status-${running === t.id ? "running" : t.status}`}>
                {running === t.id ? "Running…" : t.status === "resolved" ? "✓ Resolved" : t.status}
              </span>
            </div>
            <div className="ticket-subject">{t.subject}</div>
            <div className="ticket-meta">{TYPE_LABEL[t.type] ?? t.type} · {t.requester}</div>
            <div className="ticket-foot">
              {pending > 0 && <span className="chip attention">{pending} awaiting approval</span>}
              {t.drafts.length > 0 && <span className="chip soft">{t.drafts.length} draft{t.drafts.length > 1 ? "s" : ""}</span>}
              {!t.is_open && <span className="chip soft">closed</span>}
            </div>
          </button>
        );
      })}
    </section>
  );
}

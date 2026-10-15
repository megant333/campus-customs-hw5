import { AGENTS } from "../agents";
import type { AgentEvent } from "../types";

// Slim right sidebar: tokens per agent for the selected ticket's latest run, plus session totals.
// Numbers are the model-reported input/output tokens recorded in the audit trail.

function sum(events: AgentEvent[]) {
  const by: Record<string, { in: number; out: number; calls: number }> = {};
  for (const e of events) {
    if (e.event !== "model_response" || !e.agent || !e.tokens) continue;
    const row = (by[e.agent] ??= { in: 0, out: 0, calls: 0 });
    row.in += e.tokens.in ?? 0;
    row.out += e.tokens.out ?? 0;
    row.calls += 1;
  }
  return by;
}

const k = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

export default function TokenBar({ ticketEvents, runEvents, allEvents, ticketId }:
  { ticketEvents: AgentEvent[]; runEvents: AgentEvent[]; allEvents: AgentEvent[]; ticketId: number | null }) {
  const run = sum(ticketEvents);
  const latest = Object.values(sum(runEvents)).reduce((t, r) => t + r.in + r.out, 0);
  const session = Object.values(sum(allEvents)).reduce(
    (t, r) => ({ in: t.in + r.in, out: t.out + r.out, calls: t.calls + r.calls }), { in: 0, out: 0, calls: 0 });
  const totals = Object.values(run).reduce(
    (t, r) => ({ in: t.in + r.in, out: t.out + r.out, calls: t.calls + r.calls }), { in: 0, out: 0, calls: 0 });
  const max = Math.max(1, ...Object.values(run).map((r) => r.in + r.out));

  return (
    <aside className="tokens glass">
      <div className="panel-title"><span>Tokens</span></div>
      <div className="token-scope">{ticketId ? `Ticket ${ticketId} · all runs` : "Select a ticket"}</div>
      <div className="token-total">
        <div className="big">{k(totals.in + totals.out)}</div>
        <div className="muted">{k(totals.in)} in · {k(totals.out)} out · {totals.calls} calls</div>
        {latest > 0 && latest !== totals.in + totals.out && <div className="muted">latest run {k(latest)}</div>}
      </div>
      <div className="token-rows">
        {AGENTS.map((a) => {
          const r = run[a.id] ?? { in: 0, out: 0, calls: 0 };
          return (
            <div key={a.id} className="token-row">
              <div className="token-name"><span style={{ color: a.color }}>{a.glyph}</span> {a.name}</div>
              <div className="token-track" title={`${r.in} in / ${r.out} out`}>
                <div className="token-in" style={{ width: `${(r.in / max) * 100}%`, background: a.color }} />
                <div className="token-out" style={{ width: `${(r.out / max) * 100}%`, background: a.color }} />
              </div>
              <div className="token-num">{k(r.in + r.out)}</div>
            </div>
          );
        })}
      </div>
      <div className="token-legend"><span className="sw in" /> input <span className="sw out" /> output</div>
      <div className="token-session">
        <div className="muted">All runs on the board</div>
        <div><b>{k(session.in + session.out)}</b> tokens · {session.calls} model calls</div>
      </div>
    </aside>
  );
}

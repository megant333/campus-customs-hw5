import { AGENTS } from "../agents";
import type { AgentEvent } from "../types";

// One card per agent that worked this ticket (all runs since the last reset): the MCP tools it
// used, who it handed work to, and its latest final line (report summary / draft / boss's call).

export default function AgentSummary({ events }: { events: AgentEvent[] }) {
  const cards = AGENTS.map((a) => {
    const mine = events.filter((e) => e.agent === a.id);
    if (!mine.length) return null;
    const tools = new Set<string>();
    const handed = new Set<string>();
    for (const e of mine) {
      (e.tools ?? []).forEach((t, i) => {
        if (t === "delegate") handed.add(String(e.tool_args?.[i]?.to ?? "").replace("_", " "));
        else tools.add(t);
      });
    }
    const end = [...mine].reverse().find((e) => e.event === "agent_end");
    return { a, tools: [...tools], handed: [...handed].filter(Boolean), said: end?.said ?? "Still working…" };
  }).filter(Boolean) as { a: (typeof AGENTS)[number]; tools: string[]; handed: string[]; said: string }[];

  return (
    <section className="summary glass">
      <div className="panel-title"><span>What each agent did</span></div>
      {cards.length === 0 && <div className="empty">Run the team on this ticket to see a summary.</div>}
      <div className="summary-grid">
        {cards.map(({ a, tools, handed, said }) => (
          <div key={a.id} className="summary-card" style={{ borderTopColor: a.color }}>
            <div className="summary-head"><span className="avatar sm" style={{ background: a.color }}>{a.glyph}</span>{a.name}</div>
            <div className="summary-said">{said}</div>
            <div className="summary-tools">
              {tools.map((t) => <span key={t} className="tool-chip">{t}</span>)}
              {handed.map((h) => <span key={h} className="tool-chip deleg">→ {h}</span>)}
              {!tools.length && !handed.length && <span className="muted">no tools</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

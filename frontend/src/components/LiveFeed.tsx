import { useEffect, useRef } from "react";
import { AGENTS, describe } from "../agents";
import type { AgentEvent, AgentId } from "../types";

// Agent lanes (who is working right now and their latest line) + the step-by-step timeline.

export default function LiveFeed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const boxRef = useRef<HTMLDivElement>(null);
  // Follow new steps inside the timeline box only (never scroll the whole page).
  useEffect(() => {
    const box = boxRef.current;
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  const state = (id: AgentId) => {
    const mine = events.filter((e) => e.agent === id);
    if (!mine.length) return { status: "idle" as const, line: "—" };
    const starts = mine.filter((e) => e.event === "agent_start").length;
    const ends = mine.filter((e) => e.event === "agent_end").length;
    const lastLine = [...mine].reverse().find((e) => e.event !== "tool_results" && !e.final_output) ?? mine[mine.length - 1];
    return { status: starts > ends && running ? ("working" as const) : ("done" as const), line: describe(lastLine) };
  };
  const timeline = events.filter((e) => e.agent && e.agent !== "human" && e.event !== "tool_results" && !e.final_output);

  return (
    <section className="feed glass">
      <div className="panel-title"><span>Agents</span>{running && <span className="live">● live</span>}</div>
      <div className="lanes">
        {AGENTS.map((a) => {
          const s = state(a.id);
          return (
            <div key={a.id} className={`lane ${s.status}`}>
              <div className="avatar" style={{ background: a.color }}>{a.glyph}</div>
              <div className="lane-body">
                <div className="lane-head">
                  <b>{a.name}</b>
                  <span className={`lane-status ${s.status}`}>{s.status === "working" ? "working…" : s.status}</span>
                </div>
                <div className="lane-line">{s.line}</div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="timeline" ref={boxRef}>
        {timeline.length === 0 && <div className="empty">No agent activity for this ticket yet.</div>}
        {timeline.map((e) => {
          const a = AGENTS.find((x) => x.id === e.agent);
          const tools = (e.tools ?? []).filter((t) => t !== "delegate");
          const delegatedTo = (e.tools ?? []).includes("delegate")
            ? (e.tool_args ?? []).map((x) => x.to).filter(Boolean).join(", ") : "";
          return (
            <div key={e.id} className="step">
              <span className="step-dot" style={{ background: a?.color }} />
              <div className="step-body">
                <span className="step-agent" style={{ color: a?.color }}>{a?.name}</span>
                <span className="step-text">{describe(e)}</span>
                {tools.map((t) => <span key={t} className="tool-chip">{t}</span>)}
                {delegatedTo && <span className="tool-chip deleg">→ {String(delegatedTo).replace("_", " ")}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

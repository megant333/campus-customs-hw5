import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, api } from "./api";
import { AGENTS, latestRunEvents, money, ticketEvents } from "./agents";
import AgentSummary from "./components/AgentSummary";
import Approvals from "./components/Approvals";
import CashCard from "./components/CashCard";
import LiveFeed from "./components/LiveFeed";
import Pinball from "./components/Pinball";
import TicketBoard from "./components/TicketBoard";
import TokenBar from "./components/TokenBar";
import type { AgentEvent, Approval, Cash, NodeId, RunResult, Ticket } from "./types";

/** Append only events we haven't seen (ids are audit-trail positions, so they are unique). */
function mergeEvents(cur: AgentEvent[], incoming: AgentEvent[]): AgentEvent[] {
  const seen = new Set(cur.map((e) => e.id));
  const fresh = incoming.filter((e) => !seen.has(e.id));
  return fresh.length ? [...cur, ...fresh].sort((a, b) => a.id - b.id) : cur;
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [dateToday, setDateToday] = useState("");
  const [cash, setCash] = useState<Cash | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [feed, setFeed] = useState<AgentEvent[]>([]);
  const [feedKey, setFeedKey] = useState("live");
  const [selected, setSelected] = useState<number | null>(null);
  const [running, setRunning] = useState<number | null>(null);
  const [lastRun, setLastRun] = useState<Record<number, RunResult>>({});
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState(true);
  const since = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()]);
      setTickets(t.tickets);
      setDateToday(t.date_today);
      setCash(c);
      setApprovals(a.approvals);
      setOnline(true);
      setSelected((s) => s ?? t.tickets.find((x) => x.is_open)?.id ?? t.tickets[0]?.id ?? null);
    } catch {
      setOnline(false);
    }
  }, []);

  const pollEvents = useCallback(async (first = false) => {
    try {
      const r = await api.events(since.current, first ? 500 : 200);
      since.current = Math.max(since.current, r.next_since);
      if (r.events.length) {
        setEvents((cur) => mergeEvents(cur, r.events));
        if (!first) setFeed((cur) => mergeEvents(cur, r.events)); // history isn't replayed on load
      }
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => { refresh(); pollEvents(true); }, [refresh, pollEvents]);

  // Live while a run is going (1s), relaxed otherwise (4s). Board state every 8s.
  useEffect(() => {
    const ev = setInterval(() => pollEvents(), running ? 1000 : 4000);
    const bd = setInterval(() => { if (!running) refresh(); }, 8000);
    return () => { clearInterval(ev); clearInterval(bd); };
  }, [running, pollEvents, refresh]);

  async function runTeam(id: number) {
    setError(null);
    setRunning(id);
    setFeedKey("live");
    try {
      const result = await api.run(id);
      setLastRun((m) => ({ ...m, [id]: result }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(null);
      await pollEvents();
      await refresh();
    }
  }

  async function decide(a: Approval, decision: "approved" | "rejected", by: string) {
    setError(null);
    try {
      await api.decide(a.id, decision, by);
    } catch (e) {
      setError((e as Error).message);
    }
    await refresh();
    await pollEvents();
  }

  async function resetBoard() {
    if (!confirm("Reset the shop database to the original values?\nThe current working copy is backed up first.")) return;
    try {
      await api.reset();
      setLastRun({});
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
    await refresh();
  }

  function replay() {
    if (selected == null) return;
    setFeed(latestRunEvents(events, selected));
    setFeedKey(`replay-${Date.now()}`);
  }

  const ticket = tickets.find((t) => t.id === selected) ?? null;
  const runEvents = useMemo(() => (selected == null ? [] : latestRunEvents(events, selected)), [events, selected]);
  const allTicketEvents = useMemo(() => (selected == null ? [] : ticketEvents(events, selected)), [events, selected]);

  const active: NodeId[] = useMemo(() => {
    if (running == null) return [];
    const ev = latestRunEvents(events, running);
    return AGENTS.map((a) => a.id).filter((id) => {
      const starts = ev.filter((e) => e.agent === id && e.event === "agent_start").length;
      const ends = ev.filter((e) => e.agent === id && e.event === "agent_end").length;
      return starts > ends;
    });
  }, [events, running]);

  const result = selected != null ? lastRun[selected] : undefined;
  const pendingForTicket = ticket?.approvals.filter((a) => a.status === "pending") ?? [];

  return (
    <>
      <div className="bg" aria-hidden><span className="blob b1" /><span className="blob b2" /><span className="blob b3" /></div>
      <div className="app">
        <Pinball feed={feed} feedKey={feedKey} active={active} />

        <main className="main">
          <header className="top">
            <div className="title glass">
              <div>
                <h1>Campus Customs <span>Agent Desk</span></h1>
                <div className="badges">
                  <span className="badge">Shop date {dateToday || "…"}</span>
                  <span className="badge">Practice run · nothing is sent</span>
                  <span className={`badge ${online ? "ok" : "bad"}`}>{online ? "● backend connected" : `● backend offline (${API_URL})`}</span>
                </div>
              </div>
              <button className="btn ghost small" onClick={resetBoard} disabled={running !== null}>Reset database</button>
            </div>
            <CashCard cash={cash} />
          </header>

          {!online && (
            <div className="banner bad glass">
              Can't reach the backend at {API_URL}. Start it from <code>hw-5/backend</code> with
              {" "}<code>../.venv/bin/uvicorn main:app --reload --port 8000</code>.
            </div>
          )}
          {error && <div className="banner bad glass" onClick={() => setError(null)}>{error}</div>}

          <TicketBoard tickets={tickets} selected={selected} running={running} onSelect={setSelected} />

          {ticket && (
            <section className="focus glass">
              <div className="focus-head">
                <div>
                  <div className="muted small">Ticket #{ticket.id} · {ticket.requester}</div>
                  <h2>{ticket.subject}</h2>
                </div>
                <div className="focus-actions">
                  <button className="btn ghost small" onClick={replay} disabled={!runEvents.length || running !== null}>Replay signals</button>
                  <button
                    className="btn primary"
                    disabled={running !== null || !ticket.is_open}
                    onClick={() => runTeam(ticket.id)}
                  >
                    {running === ticket.id ? <span className="spinner" /> : null}
                    {running === ticket.id ? "Agents working…" : !ticket.is_open ? "✓ Resolved"
                      : ticket.status === "pending" ? "Run follow-up" : "Run agent team"}
                  </button>
                </div>
              </div>
              {ticket.status === "resolved" && <div className="banner ok">✓ Resolved. The team closed this ticket.</div>}
              {result && running !== ticket.id && ticket.status !== "resolved" && (
                <div className="banner info">
                  <b>Run finished → {result.decision.status}.</b> {result.decision.final_call}
                  {result.decision.needs_human.length > 0 && (
                    <ul>{result.decision.needs_human.map((n) => <li key={n}>{n}</li>)}</ul>
                  )}
                </div>
              )}
              {pendingForTicket.length > 0 && running === null && (
                <div className="banner attention">
                  The team is asking for your approval on {pendingForTicket.length} item
                  {pendingForTicket.length > 1 ? "s" : ""} ({money(pendingForTicket.reduce((s, a) => s + a.amount, 0))}).
                  Approve or reject it below, then press <b>Run follow-up</b>.
                </div>
              )}
            </section>
          )}

          <div className="work">
            <LiveFeed events={runEvents} running={running === selected && running !== null} />
            <Approvals approvals={approvals} selected={selected} busy={running !== null} onDecide={decide} />
          </div>
          <AgentSummary events={allTicketEvents} />
          {ticket && ticket.drafts.length > 0 && (
            <section className="drafts glass">
              <div className="panel-title"><span>Customer drafts</span><span className="sub">stay on the board · never sent</span></div>
              {ticket.drafts.map((d) => (
                <div key={d.id} className="draft">
                  <div className="muted small">Draft #{d.id} to {d.recipient} · {d.subject}</div>
                  <p>{d.body}</p>
                </div>
              ))}
            </section>
          )}
        </main>

        <TokenBar ticketEvents={allTicketEvents} runEvents={runEvents} allEvents={events} ticketId={selected} />
      </div>
    </>
  );
}

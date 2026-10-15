import { useEffect, useRef, useState } from "react";
import { NODE_COLOR } from "../agents";
import type { AgentEvent, NodeId } from "../types";

// Pinball-style signal map: agents are bumpers, every route between them is a lane of
// light dots. Each delegation / MCP tool call / tool result / human decision becomes a
// "ball" that lights the lane dot-to-dot from sender to receiver. Pings are queued and
// played one at a time so a burst of events still reads as a sequence.

type Point = { x: number; y: number };
type Endpoint = NodeId | "ticket";

const POS: Record<Endpoint, Point> = {
  boss: { x: 120, y: 78 },
  inventory: { x: 50, y: 196 },
  accountant: { x: 190, y: 196 },
  facilities: { x: 50, y: 330 },
  customer_service: { x: 190, y: 330 },
  mcp: { x: 120, y: 448 },
  human: { x: 52, y: 528 },
  ticket: { x: 214, y: 528 },
};
const AGENT_NODES: NodeId[] = ["boss", "inventory", "accountant", "facilities", "customer_service"];
const LABEL: Record<Endpoint, string> = {
  boss: "Boss", inventory: "Inventory", accountant: "Accountant", facilities: "Facilities",
  customer_service: "Cust. Service", mcp: "MCP server", human: "Human", ticket: "Ticket",
};
const GLYPH: Record<Endpoint, string> = {
  boss: "★", inventory: "▦", accountant: "$", facilities: "⌂", customer_service: "✉", mcp: "⚙", human: "☺", ticket: "▲",
};

const LANES: [Endpoint, Endpoint][] = [
  ...AGENT_NODES.flatMap((a, i) => AGENT_NODES.slice(i + 1).map((b) => [a, b] as [Endpoint, Endpoint])),
  ...AGENT_NODES.map((a) => [a, "mcp"] as [Endpoint, Endpoint]),
  ["human", "mcp"],
  ["ticket", "boss"],
];

const R = 22;          // bumper radius
const DOT_GAP = 11;    // px between lane lights
const STEP_MS = 26;    // light-to-light delay
const SPACING_MS = 430; // gap between queued pings

interface Ping { id: number; from: Endpoint; to: Endpoint; color: string; label?: string }

function laneDots(from: Endpoint, to: Endpoint): Point[] {
  const a = POS[from], b = POS[to];
  const dx = b.x - a.x, dy = b.y - a.y;
  const len = Math.hypot(dx, dy);
  const start = R + 6, end = len - R - 6;
  const n = Math.max(2, Math.floor((end - start) / DOT_GAP));
  return Array.from({ length: n + 1 }, (_, i) => {
    const t = (start + ((end - start) * i) / n) / len;
    return { x: a.x + dx * t, y: a.y + dy * t };
  });
}

function pingsFor(e: AgentEvent): Omit<Ping, "id">[] {
  const chain = e.chain ?? [];
  const me = e.agent as NodeId | null;
  switch (e.event) {
    case "agent_start":
      if (chain.length >= 2) {
        const from = chain[chain.length - 2];
        return [{ from, to: chain[chain.length - 1], color: NODE_COLOR[from], label: "delegate" }];
      }
      return me === "boss" ? [{ from: "ticket", to: "boss", color: NODE_COLOR.boss, label: `ticket ${e.ticket_id}` }] : [];
    case "agent_end":
      if (chain.length >= 2) {
        const to = chain[chain.length - 2];
        return [{ from: chain[chain.length - 1], to, color: NODE_COLOR[chain[chain.length - 1]], label: "report" }];
      }
      return [];
    case "model_response": {
      const tools = (e.tools ?? []).filter((t) => t !== "delegate");
      return me && tools.length ? [{ from: me, to: "mcp", color: NODE_COLOR[me], label: tools.join(", ") }] : [];
    }
    case "tool_results": {
      const res = (e.results ?? []).filter((r) => r.tool !== "delegate");
      if (!me || !res.length) return [];
      const failed = res.some((r) => r.outcome !== "success");
      return [{ from: "mcp", to: me, color: failed ? "#e05a5a" : NODE_COLOR.mcp, label: failed ? "refused" : "result" }];
    }
    case "human_decision":
      return [{ from: "human", to: "mcp", color: NODE_COLOR.human, label: "decision" }];
    default:
      return [];
  }
}

export default function Pinball({ feed, feedKey, active }: { feed: AgentEvent[]; feedKey: string; active: NodeId[] }) {
  const queue = useRef<Ping[]>([]);
  const processed = useRef(0);
  const nextId = useRef(1);
  const [lit, setLit] = useState<Ping[]>([]);
  const [hits, setHits] = useState<Record<string, number>>({});
  const [last, setLast] = useState<Ping | null>(null);

  // New feed (e.g. replay) -> start over.
  useEffect(() => {
    processed.current = 0;
    queue.current = [];
  }, [feedKey]);

  // Turn newly arrived events into queued pings.
  useEffect(() => {
    for (const e of feed.slice(processed.current)) {
      for (const p of pingsFor(e)) queue.current.push({ ...p, id: nextId.current++ });
    }
    processed.current = feed.length;
  }, [feed, feedKey]);

  // Play the queue one ping at a time.
  useEffect(() => {
    const timer = setInterval(() => {
      const p = queue.current.shift();
      if (!p) return;
      setLit((cur) => [...cur.slice(-6), p]);
      setLast(p);
      const travel = laneDots(p.from, p.to).length * STEP_MS;
      setTimeout(() => setHits((h) => ({ ...h, [p.to]: Date.now() })), travel);
      setTimeout(() => setLit((cur) => cur.filter((x) => x.id !== p.id)), travel + 900);
    }, SPACING_MS);
    return () => clearInterval(timer);
  }, []);

  const now = Date.now();
  return (
    <div className="pinball glass">
      <div className="panel-title">
        <span>Signal map</span>
        <span className="sub">{last ? `${LABEL[last.from]} → ${LABEL[last.to]}` : "waiting for a run"}</span>
      </div>
      <svg viewBox="0 0 240 560" className="pinball-svg" role="img" aria-label="Agent signal map">
        <defs>
          <radialGradient id="bumperGlass" cx="35%" cy="30%" r="75%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
            <stop offset="60%" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#f3ece0" stopOpacity="0.5" />
          </radialGradient>
        </defs>

        {/* table rails */}
        <path d="M14 548 L14 40 Q14 14 40 14 L200 14 Q226 14 226 40 L226 548" className="rail" />
        <path d="M200 548 L200 470" className="rail thin" />

        {/* resting lane lights */}
        {LANES.map(([a, b]) => laneDots(a, b).map((d, i) => (
          <circle key={`${a}-${b}-${i}`} cx={d.x} cy={d.y} r={1.6} className="dot-idle" />
        )))}

        {/* lit pings */}
        {lit.map((p) => {
          const dots = laneDots(p.from, p.to);
          const a = dots[0], b = dots[dots.length - 1];
          const dur = (dots.length * STEP_MS) / 1000;
          return (
            <g key={p.id}>
              {dots.map((d, i) => (
                <circle key={i} cx={d.x} cy={d.y} r={3} fill={p.color} className="dot-lit"
                        style={{ animationDelay: `${i * STEP_MS}ms` }} />
              ))}
              <circle r={5.5} fill={p.color} className="ball">
                <animate attributeName="cx" from={a.x} to={b.x} dur={`${dur}s`} fill="freeze" />
                <animate attributeName="cy" from={a.y} to={b.y} dur={`${dur}s`} fill="freeze" />
                <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.85;1" dur={`${dur + 0.4}s`} fill="freeze" />
              </circle>
            </g>
          );
        })}

        {/* bumpers */}
        {(Object.keys(POS) as Endpoint[]).map((id) => {
          const { x, y } = POS[id];
          const color = id === "ticket" ? "#c9b48f" : NODE_COLOR[id as NodeId];
          const isActive = active.includes(id as NodeId);
          const hit = hits[id] && now - hits[id] < 450;
          const small = id === "human" || id === "ticket";
          const r = small ? 15 : id === "mcp" ? 26 : R;
          return (
            <g key={id} className={`bumper ${isActive ? "active" : ""} ${hit ? "hit" : ""}`}>
              {isActive && <circle cx={x} cy={y} r={r + 7} fill="none" stroke={color} className="halo" />}
              <circle cx={x} cy={y} r={r} fill="url(#bumperGlass)" stroke={color} strokeWidth={isActive ? 2.6 : 1.6} />
              <circle cx={x} cy={y} r={r - 6} fill={color} opacity={isActive || hit ? 0.9 : 0.16} className="core" />
              <text x={x} y={y + 5} textAnchor="middle" className="glyph" fill={isActive || hit ? "#fff" : color}>
                {GLYPH[id]}
              </text>
              <text x={x} y={y + r + 14} textAnchor="middle" className="node-label">{LABEL[id]}</text>
            </g>
          );
        })}
      </svg>
      <div className="pinball-legend">
        {last ? (
          <span><b style={{ color: last.color }}>●</b> {LABEL[last.from]}
            {" → "}{LABEL[last.to]}{last.label ? ` · ${last.label}` : ""}</span>
        ) : <span>Pick a ticket and press Run to light up the table.</span>}
      </div>
    </div>
  );
}

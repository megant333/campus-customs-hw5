# Campus Customs Agent Desk — Design Notes

The desk is a React + Vite + TypeScript dashboard (`frontend/`) for watching the five-agent team work the ticket board and stepping in as the human approver. It talks to the FastAPI backend (`backend/main.py`) at `http://localhost:8000`. Everything is a **practice run**: drafts stay on the board, and nothing is emailed.

## Running it

```bash
# terminal 1: backend (stop the hw-4 server on :8000 first)
cd hw-5/backend && ../.venv/bin/uvicorn main:app --reload --port 8000
# terminal 2: dashboard (opens http://localhost:5173 in your browser)
cd hw-5/frontend && npm run dev
```

- The backend's CORS settings explicitly allow `http://localhost:5173` and `http://127.0.0.1:5173`, plus any other localhost port in case Vite has to pick another one.
- The API address can be overridden with `VITE_API_URL`. I used this to test against a scratch backend on port 8001.

## Layout

```
┌──────────────┬──────────────────────────────────────────────┬────────────┐
│ Signal map   │ Title · shop date · status      │ Checking $ │ Tokens     │
│ (pinball)    ├─────────────┬─────────────┬────┴────────────┤ per agent  │
│              │ Ticket 101  │ Ticket 102  │ Ticket 103      │ bars       │
│ sticky       ├─────────────┴─────────────┴─────────────────┤            │
│              │ Selected ticket · Run / Run follow-up · result banner   │ sticky     │
│              ├──────────────────────────────┬──────────────┤            │
│              │ Agents: 5 live lanes +       │ Human        │            │
│              │ step-by-step timeline        │ approvals    │            │
│              ├──────────────────────────────┴──────────────┤            │
│              │ What each agent did (summary cards)          │            │
│              │ Customer drafts (never sent)                 │            │
└──────────────┴──────────────────────────────────────────────┴────────────┘
```

- **The three panes match how you use the desk.** On the left you watch where information flows (the pinball). In the middle you act: pick a ticket, run it, approve. On the right you watch what it costs (tokens). Both sidebars are sticky, so they stay in view while the middle scrolls.
- **The ticket board is three equal cards, one per open ticket.** Each card shows a status chip (Open, Pending, ✓ Resolved, Declined, or a breathing "Running…"), a chip for anything awaiting approval, a draft count, and a "closed" tag. Click a card to select it.
- **The selected-ticket bar holds the only button that starts the team.** It changes with the ticket's state:
  - **Run agent team** for an open ticket
  - **Run follow-up** for a pending one
  - **✓ Resolved** once the ticket is closed, and the button is locked
- **Result banners appear when a run finishes.** One shows the boss's final call and its list of human actions. A gold banner appears whenever the team is waiting on your approval. A green "✓ Resolved" banner appears when the ticket is closed.

## How each requirement is met

| Requirement | Design |
|---|---|
| List all three tickets | `GET /api/tickets` feeds the ticket cards; status comes from the database, not the browser |
| Pick a ticket and start the team | Card selection, then the Run button calls `POST /api/tickets/{id}/run` |
| Show each agent and what it's saying or doing during a run | While a run is going the page polls `GET /api/events?since=` **every 1 s** (every 4 s otherwise). Five **agent lanes** show each agent's state (idle, *working…* pulsing, done) and its latest line, for example "handing off to Inventory", "calling check_stock", or the agent's own words. A **timeline** below streams every step with tool chips. It scrolls inside its own box and never moves the page. |
| Mark the ticket resolved when the run finishes | When the run returns, tickets, cash, and approvals are re-fetched, and the card and button show **✓ Resolved** if the boss closed the ticket. The server's guard rule means a ticket only resolves once nothing is pending, so a ticket waiting on approval stays **Pending** and offers **Run follow-up**. |
| Short summary of what each agent did | **"What each agent did"** has one card per agent that worked the ticket, colored by agent. Each card shows the agent's final line, its MCP tools, and who it handed off to (→ chips). It covers every run on the ticket since the last reset, so a follow-up doesn't erase what the first pass did. |
| Human approves a payment or purchase when asked | The **Human approvals** panel glows gold and the ticket bar shows a banner when something is waiting. Each card shows what is being paid, the amount, who prepared it, the reason, and the database basis for the amount. You type your name once (remembered locally), then press Approve or Reject and confirm in a dialog. Rejected or auto-rejected decisions show the server's reason. |
| Checking balance that drops after an approved payment | The **Checking balance** card reads `GET /api/cash`. After an approval the number **counts down** over 1.2 s to the new balance, and a red **▼ $2,400.00** marker appears for a few seconds. "Free for new spending" sits below it. |
| Pinball sidebar | See below |
| Token sidebar | See below |

## The pinball signal map (left sidebar)

- **The table:** an SVG pinball table with rails and a launch lane.
  - Each agent is a glass **bumper** with its own color and glyph: Boss ★ amber, Inventory ▦ sage, Accountant $ blue, Facilities ⌂ terracotta, Customer Service ✉ lilac.
  - The **MCP server** ⚙ sits at the bottom where the flippers would be. **Human** ☺ and **Ticket** ▲ are the two launch points.
- **Lanes:** every possible route is drawn as a lane of faint light dots. That covers the full mesh between agents, each agent to MCP, Human to MCP, and Ticket to Boss, matching the team's full-mesh delegation.
- **Pings:** each event becomes a "ball" that lights its lane **dot to dot** from sender to receiver, then the target bumper flashes.

  | Event | Lane |
  |---|---|
  | Ticket launched (boss starts) | Ticket → Boss |
  | Delegation | caller → teammate (caller's color) |
  | Report back | teammate → caller |
  | MCP tool call | agent → MCP |
  | Tool result | MCP → agent (gray, or **red when the server refused**, e.g. the hoodie PO blocked by unpaid invoice 501) |
  | Human decision | Human → MCP |

- **Queued playback:** pings are queued and played about 430 ms apart, so a burst of events from one poll still reads as a sequence instead of everything lighting at once.
- **Active agents** (started but not yet finished) get a pulsing halo, so you can see the whole delegation chain that's currently open, for example Boss → Inventory → Accountant.
- **Legend:** the title bar and legend show the most recent ping, for example "MCP server → Accountant · refused".
- **Replay signals** plays back the selected ticket's latest run on the table at any time, so you can re-watch a run that finished while you weren't looking.

## The token sidebar (right)

- **Big number:** total tokens for the selected ticket across all its runs since the last reset, split into input and output with a model-call count. The latest run is shown separately if there has been more than one.
- **Per-agent bars:** a light input segment and a solid output segment for each agent, in the agent's color and scaled to the biggest spender, so you can see at a glance that the boss and accountant use most of the tokens.
- **Board total:** a footer with total tokens and model calls across every run.
- **Where the numbers come from:** the model-reported token counts recorded in `output/audit_trail.json`, never estimates. **Correction (Problem 9):** my first check compared the sidebar with the same `/api/events` route it reads, so it couldn't catch a real undercount. That route dropped final-answer model calls, along with their tokens. The route was fixed, and the sidebar now matches the raw `audit_trail.json` exactly: 101 = 17 calls, 31.9k in / 2.5k out; 102 = 20 calls, 38.2k / 2.8k; 103 = 11 calls, 20.8k / 2.6k; board = 98.7k tokens, 48 calls.

## Visual theme: cream and liquid glass

- **Base:** warm cream (`#f7f1e6`) with three slowly drifting, heavily blurred color blobs (peach, sage, lavender). The blobs give the glass something to refract. Without them, frosted panels on a flat background just look gray.
- **Glass panels** are built from several layers:
  - translucent white (`rgba(255,255,255,0.46)`)
  - `backdrop-filter: blur(26px) saturate(180%)`
  - a bright 1px inner top edge, with a fainter one at the bottom
  - a soft-light specular sheen across the top-left
  - a warm brown-tinted drop shadow instead of gray, so panels sit on the cream naturally
  - 24px corner radius
- **Controls** are iOS-style pill buttons. The primary button is near-black graphite with an inner highlight, and secondary buttons are milky glass. Buttons scale down slightly when pressed.
- **Type** is the SF Pro system stack, with tight negative letter-spacing on headings and tabular numbers for money and tokens so digits don't jump while counting.
- **Color carries meaning, not decoration.** Each agent's color is reused in its pinball bumper, lane avatar, timeline dot, summary-card top border, and token bar. Status colors are blue for open, amber for pending or needs-you, green for resolved, and red for declined or refused.
- **Motion is short and purposeful:** steps fade in, working lanes pulse, active bumpers have halos, lit lanes travel, and the cash counter counts down. Nothing animates when nothing is happening.

## Data and safety choices

- **The browser only talks to the backend routes,** and the backend only reaches shop data through MCP. The browser never sees the database.
- **Approvals send `confirm: true` and a typed human name,** and the backend refuses agent role names. The browser confirmation dialog states the amount and who is recorded as deciding.
- **Reset database** is a small secondary button behind a confirmation dialog, disabled while a run is going. The backend also locks it during runs.
- **Run buttons are disabled during any run,** matching the backend's one-run-at-a-time lock, so tickets never compete for cash in parallel.
- **Polling uses `since=`,** so each poll only transfers new audit records. Events are merged by ID, so React's development double-mount can't double-count them; that was a real bug caught in testing.
- **If the backend is down,** a red banner shows the exact `uvicorn` command to start it.

## Testing

A headless Chrome (puppeteer-core) script drove the real UI against a scratch backend:
- **Ticket 102, full cycle:** run, then the approval banner and card appear. Approving counted checking down from $3,400.00 to $1,000.00 with "▼ $2,400.00". **Run follow-up** then turned the ticket **✓ Resolved** and locked its button.
- **Ticket 103, live run:** at 11 s the Boss, Inventory, and Accountant halos were all lit, and the MCP → Accountant lane flashed **red "refused"** as the server blocked the PO because of unpaid invoice 501. The lanes and timeline streamed live, and the run ended **Pending** with a customer draft on the board.
- **Replay, scroll, and errors:** Replay signals animated the table, the page didn't scroll (`scrollY` stayed 0), and there were no console errors.
- **Fixed during testing:**
  - the summary only covered the latest run;
  - the timeline auto-scroll moved the whole page;
  - the token totals double-counted under StrictMode;
  - a pinball label overlapped another.

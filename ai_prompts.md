# Homework 5 AI Prompt Log

This file records the prompts and requirements provided for Homework 5 (Campus Customs multi-agent operation). Keep it updated as the assignment develops, with one section per problem.

## Dataset notes

- `data 3/campus_customs.db` is the Campus Customs SQLite database provided for this assignment.

## Problem 1 — Vibe Coder Prompts

### Prompt typed

> ok next project do in hw 5 folder; we need to build a campus customs multi agent operation; problem 1 : vibe coder prompts, create ai_prompts.md to log as always what i say and put one section per problem with each one listing problem # and title, a prompt i typed and a follow up prompt if needed with a sentence on what was lacking after first

### Follow-up prompt

No follow-up prompt was needed for clarification.

### What was lacking in the first prompt

Nothing required correction; the folder, file name, and per-problem section structure were clearly specified.

## Problem 2 — Study the Campus Customs Database

### Prompt typed

> ok problem 2: study the campus customs database, data 3 folder is already in there to use with original shop database info; open campus_customs.db look at all table and fields and copy og file to campus_customs_new.db so later problems update THAT working copy, tell me how the three open tickets link to other tables then start output/harness.md and for each table list the fields and a short line on why that table is important to agents and we will keep growing this harness file in later problems

### Follow-up prompt

No follow-up prompt was needed for clarification.

### What was lacking in the first prompt

Nothing required correction; the source database, working-copy name, ticket-linkage question, and harness file contents were all clearly specified.

## Problem 3 — Build the MCP Server

### Prompt typed

> problem 3: build the mcp server; write mcp server in mcp_server/ using fastmcp to talk to campus_customs_new.db dont connect or run it yet we just need it for all agents later. In order to efficiently process these tickets then create the 3 most useful relevant and cost-efficient tools possible. label them clearly and never invent or hallucinate data

### Follow-up prompt

> in output/harness.md list each of the 3 tools saying which table it reads which ticket it helps unlock (101,102,or 103_ and one sentence on why its the best tool for the ticket be very specific dont just say reads inventory or someone and also add a mcp_server/README.md that explains mcp servers purpose which database file it uses and its 3 tools

### What was lacking in the first prompt

The first prompt asked for the tools themselves but did not ask for documentation mapping each tool to the specific tables it reads and the tickets it unlocks, or for a README explaining the server.

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Prompt typed

> problem 4: add the mcp server to vibe coder and test each tool; ok add the mcp server to this project so you as claude can call the tools and save the connection json text in .mcp.json at the project root and then test each tool and save evidence in output/mcp_smoke.json with info on the prompt asked for a vibe coder to call upon a tool and the tool name and then the tool output which HAS to make values from campus_customs_new.db and show/tell me it all

### Follow-up prompt

No follow-up prompt was needed for clarification.

### What was lacking in the first prompt

Nothing required correction. The one ambiguity was whether "project root" meant `hw-5/` or the workspace root that Claude Code reads, so the connection was saved in both places.

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Prompt typed

> problem 5: build the agent team and grow the mcp tools; use pydanticai to make an agentic team for campus customs we need the team to have a boss who reads each ticket and decides who works on it and makes finall calls, an inventory guy who checks stock by sku and size spots shortfalls and figures out which vendor can restock, accountant who watches cash and invoices, checks margins, and prepares payments or purchases orders for human approval, facilities guy who handles the shop space side aka leases and rent etc , and a customer service person who drafts messages for customers.

### Follow-up prompt

> we want them to delegate work with full connectivity and put the individual agent prompts in backend/prompts/ with ONE file PER agent then put data types in backend/models.py and agent files under backend/ and use my portkey and gpt-6-luna ONLY for every agent always , optimize the design of each agent to perform its job optimally with as much detail as useful for a very successfull multi agent website system and shop rules that performs each task as effectively and efficiently as possible while maintaining as low a token cost per possible

### Follow-up prompt 2

> add all optimized and efficient tools that the agents will benefit from having to the mcp server for them to work on the open tickets and use shop facts from the mcp server over data/campus_customs_new.db and do NOT invent a second shop-tools layer that bypasses mcp. Wire the agents to append to output/audit_trail.json as they run: for each agent-loop step record enough to audit later and append to this file dont wipe it each run. in output/harness.md list each agent and each mcp tool along with which table the tool uses. i want to emphasize  he tools need to update the database as tickets get resolved and make a copy of the database file thats called data/campus_customs_new.db and point the mcp server and backend at that working copy and keep campus_customs.db untouched so we can reset when we want to start resolving tickets. and then add a safety section so rules include: desk.date_today field is today for the shop,use this date to determine what is overdue; vendor lead times are from the vendors table, a vendor won't ship new product if they have an open unpaid invoice, human approval is required for any payments so ALWAYS require human approval for payments and also update the relevant table. If theres not enough cash then reject the payment always do NOT create a negative balance or debt, only worry about cash going out , before a full run to resolve tickets make sure to reset the database to the original values and do NOT ever email any customers or call real vendors EVER this is all a practice run and all drafts must stay on the board only. Sanity check all of this and add even more guardrails if necessary that the average online mulitagentic shop would have for maximum safety and efficacy while still optimizing for minimal token use. update mcp_server/readme.md so the tool list matches what we have now

### What was lacking in the first prompt

The first prompt described the five roles but didn't specify how agents delegate (boss-only versus full connectivity), where the files should live (`backend/prompts/`, `backend/models.py`), which model to use (gpt-6-luna through Portkey), or that the design should be optimized for shop rules and low token cost. It also didn't set the safety rules (human approval for every payment, no negative cash or debt, vendor blocks, shop date, practice run with no outbound messages), the audit trail, or the reset workflow, which follow-up 2 added.

## Problem 6 — Plan the 3 Tickets

### Prompt typed

> problem 6: plan the 3 tickets; before we wire the backend write down what you expect the team to do on each open ticket. build output/desk_tickets.html to be a page i can double-click with one tab per ticket (101,102, and 103) also add empty cash and reflection tabs we'll fill out in later problems. One each ticket tab fill expected section only (actual section will fill after we run the agents). For each tickets expected section tell me first what each ticket requests and a list of all the agents with their mcp tools available and then I'll tell you who i think the boss should call first and why and all the agent delegations i expect  and then which mcp tools i expect the run to use so u can put what i say verbatim in the tickets expected section

### Follow-up prompt

**Ticket 101:**

> I think the boss will first call inventory and find out using check_stock that theres no size S available right now and then accountant will request_payment_approval tool for the invoice and then request_purchase_order to rush reprint, then customer service will draft_customer_message to tell Tauhid his order will come soon

**Ticket 102:**

> ok for 102 facilities will first get called by boss because it will verify lease using get_lease_status  then accountant will use request_payment_approval

**Ticket 103:**

> then for 3 the boss calls accountant to do quote_margin then get_finance and then inventory so check_stock

### What was lacking in the first prompt

By design, the first prompt left out the predictions themselves (who the boss calls first and why, the delegations, and the MCP tools for each ticket), so they came in these follow-ups to be pasted verbatim into the page.

## Problem 7 — Backend Routes

### Prompt typed

> problem 7: backend routes
> so the react frontend dashboard (next problem) needs a backend it can call in backend/main.py use fastAPI and add routes to: return the three tickets and whether each is open or resolved, take a ticket id and run your agent team on that ticket, return recent agent events (what each agent said plus tools they used) so board can refresh, approve payment or purchase ONLY after human approval, return current checking balance from cash_accounts, reset database to original values when u want to try fresh run, from the backend/ folder start server with uvicorn main:app --reload --port 8000 this turns on your backend at http://localhost:8000 so the frontend dashboard can call those routes in output/harness.md list each route in one line (what url/what it does).

### Follow-up prompt

No follow-up prompt was needed for clarification.

### What was lacking in the first prompt

Nothing required correction. The prompt didn't say how a human proves an approval, so each approval requires a named `decided_by` plus `confirm: true`. It also didn't say what should happen when port 8000 is already in use (the hw-4 backend was running there).

## Problem 8 — Agent Dashboard

### Prompt typed

> Problem 8: Agent dashboard; build the frontend dashboard in frontend/ with react + vite + typescript, the page should call the routes you built in problem 7, the board should list all three tickets, let you pick one ticket and start the agent team on it, show each agent and what they are saying/doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay/purchase when asked, show the checking balance (drop after approved pay). I want the dashboard's look to be a nice clean theme, a cream color background with similar to an ios liquid glass aesthetic. make the front end talk to the backend at http://localhost:8000 on the backend, allow the vite page origin (usually http://localhost:5173) so the browsers allowed to call those routes. start board with npm run dev to open the react desk in my browser so i can pick tickets and watch the agents. write output/design.md for my dashboard choices. I want a sidebar that shows almost like a pinball machine layout that lights up from dot to dot showing how the information pings from the boss to one of the agents to another and have another little sidebar that shows token usage

### Follow-up prompt

No follow-up prompt was needed for clarification.

### What was lacking in the first prompt

Nothing required correction. The prompt didn't say what "resolved when the run finishes" should mean for a ticket that is still waiting on a human approval. Because the safety rules don't allow resolving with pending approvals, such tickets show **Pending** with a **Run follow-up** button and resolve after the approval.

## Problem 9 — Resolve the Tickets

### Prompt typed

> problem 9: resolve the tickets; first reset the working database data/campus_customs_new.db again to start clean, note starting checking balance then run all 3 tickets on the board until theyre resolved then open output/desk_tickets.html and fill problem 6's actual section on which agents worked and what they delegated and which tools were used and compare the expected section and let me know. then on cash tab of the same output/desk_tickets.html itemize the money, start checking balance (after reset) and for each ticket list how cash changed when ticket resolved and why (pay, purchase, dollar amount speicificed), ending checking balance (match cash_accounts in working database). wrong cash math loses points so do it right, also save output/resolved_tickets.json where for each ticket we have id, final status, short outcome, contribution from each agent, human approvals, and then output/resolved_board.html thats a page i can double click with a screenshot of the react board with each resolved ticket then append real runs to output/audit_trail.json then finish output/harness.md so it covers tables, mcp tools, five agents, api routes, dashboard, safety.

### Follow-up prompt

> Approve both (Recommended)  *(answer to the approval question for rent $2,400 and invoice 501 $840)*
>
> ok can you finish this

### What was lacking in the first prompt

It didn't say who gives the human approval for the payments, which the safety rules require. I asked, and you approved both. It also didn't say what "resolved" should mean for tickets that wait on a restock or a customer reply, which can never happen while the shop date is frozen. "Resolved" was defined as the team's work being done, with outside waits noted.

## Problem 10 — Reflection

### Prompt typed

> problem 10: reflection: open output/desk_tickets.html and show me the whole dashboard and everything so i can interact fully and then fill the reflection tab with what i tell you on these categories: how would i evaluate the performance of the agents on each ticket and why, for each ticket how did actual compare to my expected plan, what wouldve been simpler as one agent with tools and why, three new problems campus customs might face that this agent team could solve with tools build, three new problems campus customs might face that this agent team couldnt solve with tools built here and what tools would be needed to solve those problems  ; tie every answer to this app and the three tickets we ran, use ticket tabs and cash tab on same page as evidence.

### Follow-up prompt

> it all looks good but open the reflection tab for me i dont see it

> ok so how id evaluate performance is how many runs model calls and tokens it takes, the boss should correctly send everything to the right place the first time and then they should be able to delegate across each other efficiently with all of them aware of the bosses plan with awarness of what the others do and not have to constantly send it back to the boss to decide the next step and instead of burning tokens when it gets stuck it should just pause and ask the human for the next call if it doesnt immediately know what to do next or encounters an issue since the human is still hired to do this too by approving everything.  For each ticket I was pretty accurate on who and what would get used but with some small changes in order for the reality. What wouldve been simpler with one agent is that all these handoffs take extra time and money by resending prompts and tool definitions and theres chekcing. its good that specialists know what to do and that they caught errors like a duplicate reprint but optimizing this I would try to utilize some kind of token caching and memory to same time and tokens long term. Three new problems could be customer_order, rent_notice, or price_override tickets, new problems the team cant solve would be recording a sale I think the accountant would need a record_revenue function and inventory needs to recieve_stock and also inventory and accountant would need to process_refund and return_stock for refunds/returns to the store

> ok can you add these things to it too by saying for example: and then put in quotes " " those parts of the responses where they need to be

### What was lacking in the first prompt

By design, the first prompt left the reflection answers themselves for this follow-up, to be pasted verbatim. The first follow-up was needed because the browser tab had been opened before the Reflection tab was added, so it had to be reopened on that tab.

---
name: system-diagram
description: >-
  Draw any system, funnel, workflow, client engagement or agent pipeline as an editable
  FigJam diagram anyone can read in 30 seconds: plain words, owners in the labels, colored
  by status (built / waiting on someone / not started). Default = ONE overview diagram,
  fast, no questions. "full" (or a system too big for one diagram) = the same board plus
  zoom-ins: step by step, decisions, who does what. Built only from the system's real
  files, never from memory. Triggers: "/system-diagram", "system diagram", "diagram this
  system", "map how this works", "draw me how this works", "I can't keep up with this
  system", "make a diagram of <project>".
---

# /system-diagram

One FigJam board per system. Fast by default. The Mermaid source is saved next to the
project, so the board can be regenerated and diffed when the system changes.

## FIRST RUN: onboarding gate
If `.onboarded` does NOT exist in this folder, run `bash doctor.sh` first (Windows:
`powershell -ExecutionPolicy Bypass -File doctor.ps1`), then check the one thing doctor
can't: the **Figma connector** (`figma_mcp`).
1. Look for the Figma MCP tool `generate_diagram` in your tool list. If it's there, it's ✅.
2. If not: say it's what draws the board, and send them to
   <https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/> (Figma's MCP server guide).
   In Claude Code the easiest route is Figma's plugin,
   `claude plugin install figma@claude-plugins-official` (it also brings Figma's diagram
   skill); the manual route is
   `claude mcp add --transport http figma https://mcp.figma.com/mcp`. Then restart Claude
   Code, run `/mcp`, pick figma and authenticate. A free Figma account works for FigJam drafts.
   Re-check for `generate_diagram`; help them retry until it shows.
3. Only if their Figma account has more than one team or plan: ask once which one new
   boards go to and save its key (looks like `team::123...`; Figma's tool lists them) as
   `plan_key` in `config.local.json` in this folder (copy `config.example.json`). Never
   ask again after that.
When `generate_diagram` is available, write `.onboarded` (`date > .onboarded`) and ask
which system to draw.

---

## 1. Gather the real system first
- Use what's in context: the conversation, the project README, handoff or status notes,
  memory, repo code and handlers, skill files, config.
- If context is thin, read those sources before drawing. Grep, don't recall.
- Never invent steps, tools or owners to round it out. Leave out what you can't confirm
  and list the gaps.
- Look for an existing board for this system (README, notes, memory). If one exists, add
  to it with its `fileKey`; never a second board for the same system.

## 2. Shape it
- Mermaid `flowchart LR`, grouped into 4 to 7 numbered subgraphs in the order things
  happen (for example 1. Discover, 2. Book, 3. Prepare, 4. Serve, 5. Follow up).
- 12 to 25 nodes. Bigger = one overview + zoom-ins (section 5).
- Shapes:
  - stadium `(["..."])` start and end states
  - diamond `{"..."}` decisions and routing
  - cylinder `[("...")]` data stores (CRM, spreadsheets, databases)
  - subroutine `[["..."]]` automated jobs or engines
  - parallelogram `[/"..."/]` forms and inputs
  - plain rectangle for everything else
- Owner inside the label when it's a person: "Priya reviews draft", "Nightly sync job".
- Edges: solid = main path. Dotted `-.->` = async or blocked, with a 1-3 word label
  ("Needs key"). Decision branches carry the rule ("repair over 1 hour").
- Plain words: "Booking form", not a file path; "about a dollar", "about 7 min".
- No emojis, no `\n`, no HTML, camelCase node ids, quote every label, never the word
  `end` in a class name.

An example source is in `reference/example.mmd` (an invented bike repair shop booking flow).

## 3. Color by status (always, unless it's a static map with no status)
```
classDef built fill:#D9F2E3,stroke:#2E8B57
classDef waiting fill:#FFF1C9,stroke:#C99A00
classDef todo fill:#ECECEC,stroke:#888888
```
green = built or running · yellow = waiting on the user or someone else · gray = not started.

## 4. Generate
- If a `figma-generate-diagram` skill is installed (it ships with Figma's Claude plugin),
  load it before every `generate_diagram` call.
- Save the Mermaid to `<project>/docs/diagrams/NN-<name>.mmd` (no project folder:
  `${SYSTEM_DIAGRAM_HOME:-~/diagrams}/<slug>/`). The `.mmd` is the source of truth; the
  board is a rendering.
- Call `generate_diagram`. If `config.local.json` has a `plan_key`, pass it as the
  `planKey` argument (format `team::<digits>` or `organization::<digits>`; when the account
  has more than one plan, Figma's tool lists them so the user can pick). Use the name "<System name> system, MM/DD/YY". Later diagrams for the same system: same
  `fileKey`.
- New boards land in the user's Figma drafts; moving them into a project folder is a
  manual step in Figma. Say so once.

## 5. "full" mode (or a system too big for one diagram): zoom-ins on the same board
Add only what applies, each 8-15 nodes, same colors and rules:
1. Step by step: one run, start to finish, numbered, where it waits on a human.
2. Decisions: every branch and the rule behind it (`flowchart TD`, diamonds).
3. Who does what: subgraphs per owner (the user / Claude / tools / other people) and the
   handoffs.
4. Where things live: stores, files and services, and what reads or writes each.

## 6. Reply (short)
- the FigJam link
- the color legend in one line
- what's yellow (waiting on someone) as a short list
- any gaps you left out, and the sources it was built from, in one line
Then write the board link into the project README ("Diagram: <link>") if there is one.

## Rules
- Client-facing diagrams never mention the tools used to make them (Figma, FigJam,
  Claude) in the diagram or in any text sent with it, unless the user asks.
- Don't repeat the shape's meaning in its label ("CRM", not "Database: CRM").
- The user can steer with FigJam comments: read them, make the change, reply to each.
- Keep it current: when the system changes, update the `.mmd` and regenerate that
  diagram into the same board. A stale diagram is worse than none.
- If the user dislikes it twice, stop regenerating. Ask what's wrong, or suggest they
  edit it in FigJam directly.

---
Free from Rise Growth Marketing (risegm.com/skills). CC BY 4.0, see `LICENSE.txt`.
Feedback or bugs: open an issue at github.com/alvinrgm/skill-shop.

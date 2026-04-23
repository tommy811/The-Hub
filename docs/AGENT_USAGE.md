. How to actually use this, day to day
Every session starts the same way
Open Claude Code. That's it. CLAUDE.md is auto-loaded — the Database Query Protocol is already in context. No prompting needed.
What you should notice: Claude will now ask before guessing column names. If it doesn't — if it writes is_primary or similar confidently — that's a signal to push back: "Check docs/SCHEMA.md first." Over a few sessions this becomes automatic.
Before writing any feature that touches the DB
Don't regenerate schema every session. Do regenerate when:

You just ran a migration
You pulled from git and see new files under supabase/migrations/
Claude Code mentions a column that surprises you (might be stale types)
It's been a week and you can't remember

bashnpm run db:schema     # updates docs/SCHEMA.md
npm run db:types      # updates TS types
If anything changes, commit those files. They're the ground truth — stale ground truth is worse than no ground truth.
When building UI
Write normally. Don't invoke the UI skills proactively — they're there when you need a second opinion.
Invoke the audit when:

You finish a new route or major component and before you move on
Something looks off and you can't articulate why
Before shipping to a user

Use the skill by name in a prompt:

Run the web-design-guidelines skill against app/creators/page.tsx and components/creators/stat-card.tsx. Report findings as a list. Don't fix anything — I just want to see what's wrong.

For accessibility specifically:

Run the a11y-audit skill on http://localhost:3000/creators. I want the axe-core findings, categorized by severity.

Don't run them on every edit. They're for moments of reflection, not moments of flow.
The Stop hook does what it does
When you end a session, the hook runs typecheck + lint + (eventually) Playwright. If something fails, Claude Code can't end the turn — it has to fix it first. This is the 80% of the value for 20% of the setup.
If the hook is blocking something you know is fine (false positive), you can bypass by running exit explicitly in the Claude session — but don't make a habit of it. The hook is there to catch you on a tired day.
When something bites you anyway
Three patterns will emerge over the next few weeks. Each has a fix, and each fix is small.
Pattern 1: Claude still hallucinates a column.
Root cause: SCHEMA.md is stale or too long for context.
Fix: npm run db:schema, and if the file is >300 lines, tell Claude "summarize docs/SCHEMA.md into just the tables we're touching this session" and work from the summary.
Pattern 2: A 22P02 error hits the DB anyway.
This is your signal it's time to add the Pydantic strict-enum layer from Part B of the research report. Not prophylactically — reactively, when it bites. Maybe 15 minutes of work at that point.
Pattern 3: UI drift creeps back in.
Signal: you're reviewing a PR and see p-[17px] somewhere. Time to add eslint-plugin-tailwindcss with no-arbitrary-value: error. Again ~15 min, reactive not proactive.
What you should NOT do

Don't install more skills unless one of the Pain Points bites in a way the current setup can't catch. More agents = more ways to be wrong.
Don't regenerate docs/SCHEMA.md on every commit. Manual is correct for your scale.
Don't try to fix all four drift items in PROJECT_STATE.md §20 this week. They're tracked. Phase 2 will force the question naturally.
Don't second-guess the autonomy boundary. Read-only verifier + manual audit invocation is what a 2–5 person team should run. Auto-fix creates more problems than it solves at this scale.

When to revisit
Set a calendar reminder for 8 weeks out (mid-June). Check:

How many times has the Stop hook caught a real bug? (Pattern should emerge.)
How many times has Claude asked a schema-clarifying question instead of guessing?
How much time did you lose to UI inconsistency sessions?

If the answers are "lots, lots, none" — the system is earning its keep, don't touch it.
If the answers are "rarely, never, still losing time" — something's wrong with adoption, not the setup. Come back and we'll diagnose.
The short version

Just open Claude Code and work. The rules apply automatically.
npm run db:schema && npm run db:types after migrations.
Invoke UI skills by name when you want a review — not on autopilot.
Let pain drive the next investment. Don't build ahead.
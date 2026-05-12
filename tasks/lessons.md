# Workflow Orchestration Best Practices

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update 'tasks/lessons.md' with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

### 7. Polymarket API State Nuances
- **Pattern Corrected:** Inner markets within an active event can be resolved or inactive. Checking `event['closed'] == false` or `event['active'] == true` is NOT enough.
- **Rule:** Always verify inner market `active` state (`m.get('active') == True`) in addition to checking for `m.get('closed') == False` and that the specific event lacks a `status == 'resolved'` flag before assuming it is a tradeable "live" money opportunity.

### 8. Sports Market Resolution & Ground Truth Verification
- **Pattern Corrected:** Relying solely on the Polymarket API status for sports markets can lead to false positives where games are finished but the market remains "active".
- **Rule:** For all sports-related markets (NBA, EPL, etc.), cross-reference with a live Ground Truth source (Scraper, Scoreboard API, or Subagent search) to confirm the game hasn't ended. Never assume a market is tradeable just because the API hasn't flipped the `resolved` flag yet. Always verify if the outcome is already public knowledge.

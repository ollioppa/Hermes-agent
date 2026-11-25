# Adaptive discovery questions

The seven perspectives in `SKILL.md` are lenses for the agent, not a script to read aloud. Derive each question from the user's wording, a relevant source, or the previous answer. Before asking, identify what different replies would change in the report's answer or task handoff. If no plausible reply would change it, move on. A ticket or workspace is optional; never ask the user to repeat a fact already available there.

## Start from the actual request

| Starting situation | Useful first uncertainty | Follow the answer |
| --- | --- | --- |
| “How can I use IssueTracker effectively and save time?” | Which IssueTracker activity costs this person time? | If finding work is the issue, ask how they currently find it and what could be missed. If status reporting is the issue, ask what they must report and to whom. Do not prescribe a filter before knowing the bottleneck. |
| “Best practices for a secrets service with infrastructure-as-code and maintenance” | Is the user planning a new setup or asking about an existing one? | For an existing setup, inspect relevant infrastructure code and configuration if available. For a general design question, explain design decisions and operational ownership. Maintenance is already in the request; do not ask whether it is in scope. |
| “How do I build a team skill with value for everyone?” | Is there a repeated task or failure the skill should address? | If yes, examine that workflow and its current prompt or instructions. If no candidate exists, explain how to find one; do not invent a team's pain point. |
| Concrete ticket or code change | Which requirement, boundary, or observed behavior is still uncertain after reading relevant sources? | Cite what is known, then ask about the interpretation or decision the sources cannot make. |

## Use the seven lenses selectively

- **Goal:** Separate the requested method from the outcome only when the distinction could change the work. “Move the report” may really mean “make it accessible.”
- **Success:** Ask for an observable result when “better” or “done” would make acceptance ambiguous. A general advice question may need “What would be useful to you?” rather than a metric.
- **Scope:** Clarify the boundary that the request actually exposes. Do not demand exclusions where none matter.
- **Current state:** Distinguish user recollection, ticket claim, inspected file, and executed check. For a source-free question, say what has not been inspected once, then continue.
- **Gap / change:** Ask what blocks the outcome when a specific change is contemplated. Do not assume every question requires implementation.
- **Constraints:** Bring forward the one condition that could reverse the answer, such as compatibility, access, deadline, or recovery. Do not recite a fixed list.
- **Approach:** Propose a sensible answer or first step and invite correction; do not require the user to design the whole plan.

An answer can resolve several lenses at once. A new reply can also expose a deeper issue within the same lens. Stop asking when the next answer is unlikely to change the useful result. In the final report, show how the applicable perspectives were resolved or left open without reproducing seven separate questions.

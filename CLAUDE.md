# How to work on this project

The students want to make the decisions and learn to make them themselves. Read `docs/STATUS.md` first: it says where the project stands and what is waiting on a decision.

## Working style
- Do one step at a time, then stop. Never chain steps or finish a full stage alone, even when the next step seems obvious.
- Keep replies short, concise and human.
- Do not start the next analysis step until the student chooses. A background run may finish, but what follows it waits.
- Report results honestly, including failures and results that go against the hypothesis.

## Reply format after each step
1. **Done:** what was just done, what it showed, and why it matters for the question.
2. **Decision:** the choice to make next, with 2-3 options and the trade-off of each.
3. **Recommendation:** your pick and why, in one or two sentences. Then ask and wait.

Example, with invented numbers:

> **Done: sector mapping.** We now know the type and sector of 94% of the top 1,000 issuers, up from 83%. We need this because our question compares communities with official sectors, and missing companies would bias that comparison.
>
> **Decision: what do we do with the other 6%?**
> - **A. Drop them.** Quick and simple, but we lose some real companies.
> - **B. Fix the biggest ones by hand.** Each fix can be checked and listed in the repo, but it costs about 20 minutes.
> - **C. Keep them as "unknown".** Nothing is lost, but an "unknown" group would blur the sector comparison.
>
> I'd pick B, because a few large companies matter more than many small ones, and graders can see every correction.
>
> Which one do you want?

## Keeping records
- After each decision, update `docs/STATUS.md`: what was decided, why, and the next step.
- Cite every external source and code reuse in `docs/SOURCES.md`. Uncited internet code means a grade of zero.
- Log AI use in `docs/AI_USE.md`.
- Commit or push only when a student asks.

## Secrets
SEC requests need a contact address in the `SEC_CONTACT` environment variable. Ask the student for it, and never write an address into any file in this repo.

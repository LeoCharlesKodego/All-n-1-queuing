# PROMPTS.md — Prompts for the coding agent

Put `AGENTS.md`, `SPEC.md`, `PLAN.md`, `DECISIONS.md` in the project root first. The rules, phases, stop conditions, and token rules live in those files, so the prompts stay short.

---

## 1. Start prompt (the only prompt needed to build everything)

```
Read AGENTS.md, SPEC.md, PLAN.md, and DECISIONS.md in the project root, once, in full, in that order. They are the whole brief.

Then build the entire project, Phase 1 through Phase 7, in order, without waiting for me between phases. Follow AGENTS.md strictly, especially section 8 (running phases without prompts) and section 9 (token economy).

For each phase: build it, verify every feature live by running it, tick PLAN.md, add a short Progress log entry, commit, and start the next phase.

Stop and ask me only for the conditions listed in AGENTS.md section 8. Anything needing real hardware (for example the thermal printer) or my input: build around it, mark it [pending user], and keep going.

Keep chat replies minimal. When all 7 phases are done, send the final report (max 25 lines).
```

---

## 2. Resume prompt (if the session stops or the context resets)

```
Read AGENTS.md and PLAN.md (use the Progress log), and check git status. Continue from the first unticked task. Do not re-read SPEC.md or DECISIONS.md in full; open only the sections you need. Same rules as before: verify live, short replies, continue through all phases.
```

---

## 3. Quality-control review (use when you want a strict check, in a fresh session)

```
Review the project as a strict reviewer, not as the author. For each phase in PLAN.md that is ticked:
1. Compare what exists against the tasks and exit criteria and the matching SPEC.md sections. List anything missing or different.
2. Check AGENTS.md rules: hardcoded user-facing text, internet dependencies, queue logic outside the server module, missing server-side role checks, silent deletions, scope creep.
3. Run each exit criterion live and report exactly what you observed. If you cannot run one, say so.
Do not fix anything. Report only, as a short list.
```

---

## 4. Concurrency check (run after the core queue is built)

```
Write and run a test where several counters call next at the same instant against the same waiting tickets, repeated many times, with priority tickets mixed in. Report whether any ticket was ever given to two counters, whether priority mode behaved as specified, and whether any ticket was skipped or lost. Show the actual output, trimmed to the relevant lines.
```

---

## 5. Proposing a change (when something in the plan looks wrong)

```
Stop. Do not implement a workaround. Describe the problem, which SPEC.md or DECISIONS.md item it affects, your options with trade-offs, and your recommendation. Add it to DECISIONS.md as a Proposed entry. Wait for my decision.
```

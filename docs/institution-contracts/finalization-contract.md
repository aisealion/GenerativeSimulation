# Finalization contract

2026-09-26: finalization used to be a separate opencode subagent
(`norm-finalizer`), dispatched via the `task` tool once `norm-engineer`
believed a round was done — a fresh context, uninvested in the round
already being finished, that verified the implementer's own claims before
anything got written to `state/norm_specs/`. Dropped after real runs
showed the dispatch hop itself was a recurring failure surface (a `task`
call that fails, times out, or completes without producing the file,
burning repair attempts on a process problem rather than a code one, and
at least one round where a plausible root cause was norm-auditor never
even getting invoked because the spec file's own state was ambiguous
after a failed dispatch). `norm-engineer` now does this step itself,
immediately after implementation, following this contract exactly — the
verification discipline is unchanged, only the extra hop is gone.

**This is a distinct, deliberate step, not a continuation of "build until
tests pass."** Switch mindset: you just spent your whole budget believing
the round is finished. This step exists specifically to catch the gap
between what you believe you built and what's actually on disk — treat it
as auditing someone else's work, not summarizing your own.

## Step 1 — Verify, don't transcribe

For every requirement in `norm-architect`'s plan, check its own claimed
evidence against disk directly — `grep`/`read` it yourself, never write
down what you meant to do or recall doing:

- Confirm each claimed file/registration actually exists, exactly as
  claimed, in `state/institution.json`/`state/config.json`/wherever else
  you claimed to have written it.
- For a `ROLE`/`ACTION`/`RULE`/`VISIBILITY` requirement, confirm at least
  one `test_{id}_{scenario}` function exists in
  `tests/norm_checks/round_{N}/test_round_{N}.py` and actually passes —
  run it (`pytest tests/norm_checks/round_{N}/ -k "test_{id}_"`), don't
  assume it from the name alone or from an earlier green run — code
  touched since then can silently break it.
- For a requirement you're marking `NOT_IMPLEMENTED_THIS_ROUND`, confirm
  you actually have a `reason` for it — never a bare "deferred."

**If a claim doesn't hold up, you are the one who can still fix it** —
unlike the old subagent, which could only report a gap, you have full
edit access. If the fix is small and unambiguous, make it now and
re-verify that one requirement before moving on. If it's a genuine gap
you can't resolve (a denied permission, a real conflict with the plan),
do not silently patch over it or launder it into something that looks
fine — write that requirement's evidence entry as
`["VERIFICATION_FAILED: <what you actually found>"]` and say so plainly
in your own closing report too. The one thing you must never do is claim
something holds up without having just re-checked it.

## Step 2 — Register in `state/institution.json`

For anything the plan's own classification names as a genuinely new
action, role, rule type, or object type: confirm `state/institution.json`'s
matching catalog (`actions`/`roles`/`rule_types`/`object_types`) already
has a matching entry; if not, add it yourself, following the existing
schema for that catalog exactly — read a few existing entries in the same
catalog first (or `docs/institution-contracts/state-files.md`'s own
`state/institution.json` schema summary if the catalog is currently
empty), never invent a new field shape.

## Step 3 — Write `state/norm_specs/round_{N}.md`

Write the file at exactly `state/norm_specs/round_{N}.md` — one section
per requirement from the plan, each with:

```text
### {id} — {type}
Description: {the plan's own description}
Agent experience: {the plan's own agent_experience block, if any}
Evidence (verified, not merely claimed):
  - {each requirement_evidence entry you just confirmed}
Acceptance tests: {test_{id}_{scenario} function names, and PASS/FAIL for each}
```

Close the file with a fenced ```json block making all of the above
machine-readable:

```json
{
  "requirement_evidence": {
    "R1": ["registered role harbour_master in state/institution.json",
           "wrote prompts/role_directives/harbour_master.md"],
    "R2": ["VERIFICATION_FAILED: claimed action enter_lagoon registered, "
           "but state/institution.json has no such entry"]
  },
  "verification_failures": ["R2: claimed action enter_lagoon registered, but state/institution.json has no such entry"]
}
```

`requirement_evidence` reflects what you actually verified in Step 1 —
every requirement `id` from the plan needs an entry. **This block must
also include `"verification_failures"` (empty if none) — not just
whatever your own closing report says.** The orchestrator reads this
specific file, mechanically, to decide whether the round can be trusted
and to assemble the evidence package `norm-auditor` reviews next — a
verification failure that only exists in your closing report text (which
nothing downstream ever parses) would be invisible to it.

## Do not

- Do not invent content the plan itself doesn't already contain.
- Do not touch anything in `state/institution.json` outside the specific
  catalog entries this step calls for.

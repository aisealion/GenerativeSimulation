# Compiles state/institution.json's action catalog into state/schedule.json
# — the ordering used to live only as the literal key order of a
# hand-maintained schedule.json file, with no check that it actually
# matched what each action's own design said about its position. Now each
# ActionSpec states its own `scheduling.after`/`before` constraint, and this
# module resolves them into an order via a stable topological sort — a
# conflict (an unknown action named, or a genuine cycle) is a
# SchedulingConflictError, caught by the same repair loop as a compile
# error, rather than a silent ordering mismatch nobody checks.
#
# Output format is UNCHANGED from today's hand-maintained state/schedule.json
# ({action_name: gate_condition}, dict order = execution order) — every
# existing reader (engine/simulate.py's load_schedule()/evaluate_gate())
# needs zero changes.

from collections import defaultdict


class SchedulingConflictError(Exception):
    pass


def compile_schedule(action_specs):
    """`action_specs`: {name: ActionSpec dict}, in the order they should be
    considered when nothing else constrains them (ties are broken by this
    insertion order, so the result is deterministic and reproducible from
    the same institution.json). Each spec's `scheduling.after`/`before`
    (both optional, either or both may be set) names another key in
    `action_specs`. Returns an ordered {name: gate} dict."""
    names = list(action_specs)
    name_index = {name: i for i, name in enumerate(names)}

    successors = defaultdict(set)  # name -> names that must come after it
    indegree = {name: 0 for name in names}
    for name, spec in action_specs.items():
        scheduling = spec.get("scheduling", {})
        pred = scheduling.get("after")
        if pred is not None:
            if pred not in action_specs:
                raise SchedulingConflictError(
                    f"{name!r}'s scheduling.after names unknown action {pred!r}"
                )
            successors[pred].add(name)
        succ = scheduling.get("before")
        if succ is not None:
            if succ not in action_specs:
                raise SchedulingConflictError(
                    f"{name!r}'s scheduling.before names unknown action {succ!r}"
                )
            successors[name].add(succ)
    for name in names:
        for target in successors[name]:
            indegree[target] += 1

    ready = [name for name in names if indegree[name] == 0]
    ordered = []
    remaining_indegree = dict(indegree)
    while ready:
        ready.sort(key=lambda n: name_index[n])  # stable: earliest-declared ready node first
        current = ready.pop(0)
        ordered.append(current)
        for target in successors[current]:
            remaining_indegree[target] -= 1
            if remaining_indegree[target] == 0:
                ready.append(target)

    if len(ordered) != len(names):
        cyclic = sorted(set(names) - set(ordered))
        raise SchedulingConflictError(
            f"cycle detected among action scheduling constraints, involving: {cyclic}"
        )

    return {name: action_specs[name].get("scheduling", {}).get("gate", "true") for name in ordered}

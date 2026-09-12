# Institutional structural-change history — the version/history side of
# the design this project's own institution.json was modeled on: a
# monotonic "version" answering "which shape of the institution was this,"
# and an append-only log answering "what changed and when," independent
# of git log (which mixes in every other kind of commit) and
# state/norm_specs/ (which records design *reasoning*, not a terse
# structured diff). Pure diffing logic only — no file I/O, no knowledge of
# git or round numbers; engine/simulate.py owns wiring this to both.

CATALOGS = ("actions", "roles", "norm_types", "object_types")


def diff_institution(old, new):
    """Every structural difference between two institution.json dicts,
    across the four catalogs (actions/roles/norm_types/object_types) plus
    the "state" schema dict. Returns a list of
    {"kind": "<catalog>_added"|"<catalog>_removed"|"<catalog>_changed",
    "name": ..., "before": ..., "after": ...} — empty if nothing
    structural changed (e.g. a purely parametric round that never touched
    institution.json at all)."""
    changes = []
    for catalog in CATALOGS:
        changes.extend(_diff_catalog(catalog, old.get(catalog, {}), new.get(catalog, {})))
    changes.extend(_diff_catalog("state", old.get("state", {}), new.get("state", {})))
    return changes


def _diff_catalog(catalog, old_entries, new_entries):
    changes = []
    old_names = set(old_entries)
    new_names = set(new_entries)
    for name in sorted(new_names - old_names):
        changes.append({"kind": f"{catalog}_added", "name": name, "before": None, "after": new_entries[name]})
    for name in sorted(old_names - new_names):
        changes.append({"kind": f"{catalog}_removed", "name": name, "before": old_entries[name], "after": None})
    for name in sorted(old_names & new_names):
        if old_entries[name] != new_entries[name]:
            changes.append({
                "kind": f"{catalog}_changed", "name": name,
                "before": old_entries[name], "after": new_entries[name],
            })
    return changes

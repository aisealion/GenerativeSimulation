# ObjectRuntime: the institutional-object layer (pools, ledgers, tools).
# Backed by three things, deliberately kept as separate as
# state/config.json's rules are from their own runtime state:
#
#   - state/object_types/*.json — the declarative ObjectSpec (ownership/
#     fields/operations/permissions/visibility). Ships empty by default,
#     same "no seed content" principle as actions/rules/.
#   - state/objects.json — DECLARATIONS only ({"id", "type", "lifecycle"?}),
#     norm-implementer-owned, exactly like state/config.json["rules"][action_name]'s
#     own entries — never mutated by the running simulation.
#   - state["runtime"]["objects"][object_id]["fields"] — the actual mutable
#     field values, simulation-owned, mirroring runtime["rules"][key]'s own
#     role as a rule's cross-round-persistent state. Lazily seeded from the
#     type's own field defaults the first time an object is touched.
#
# Conflating declaration and mutable state in one implementer-writable file
# is exactly the failure shape this project's config.json/runtime.json
# split already exists to avoid — see CLAUDE.md's own history for why
# state/runtime.json stays off the norm-implementer's tracked paths.
#
# Every generic operation (deposit/withdraw/set/append/read) is
# permission-checked against the object type's own declared `permissions`;
# a type may also name a `custom_handler` (a filename stem under
# objects/handlers/, the Level-3 escape hatch) for behavior the five
# generic operations can't express — that handler is responsible for its
# own permission checking, since it isn't one of the fixed operations
# OPERATION_PERMISSION knows about.
#
# A mutation never itself becomes a fact — a field's current value is
# read live (via read(), which already applies the type's own per-field
# visibility), not cached as a fact that could go stale. Only the
# *announcement* of a mutation (when the caller supplies `narration`)
# becomes an Event (state/events.json, via ctx.events.emit() — see
# engine.institution.events), so it reaches render_notices()/memory for
# exactly the round it happened and never lingers.

from roles.roles import current_holder
from engine.institution.events import Event, Visibility
from engine.institution.registry import discover_handlers

OPERATION_PERMISSION = {
    "deposit": "WRITE",
    "withdraw": "WRITE",
    "set": "WRITE",
    "append": "APPEND",
    "read": "READ",
}


class ObjectPermissionError(Exception):
    pass


class ObjectRuntime:
    def __init__(self, object_types, declarations, runtime_objects, fluents, round_number, events):
        self.object_types = object_types  # {type_name: ObjectSpec dict}
        self.declarations = declarations  # state["objects"] list — {"id", "type", "lifecycle"?}
        self.runtime_objects = runtime_objects  # state["runtime"]["objects"] — {id: {"fields": {...}}}
        self.fluents = fluents
        self.round_number = round_number
        self.events = events  # an engine.institution.events.EventEmitter

    def _declaration(self, object_id):
        for decl in self.declarations:
            if decl["id"] == object_id:
                return decl
        raise KeyError(f"no institutional object with id {object_id!r}")

    def _spec(self, declaration):
        return self.object_types[declaration["type"]]

    def _fields(self, object_id, spec):
        """The mutable field dict for this object, lazily seeded from the
        type's own declared defaults on first touch — never pre-populated
        by a norm-implementer edit to state/objects.json itself."""
        record = self.runtime_objects.setdefault(object_id, {})
        fields = record.setdefault("fields", {})
        for field_name, field_spec in spec.get("fields", {}).items():
            fields.setdefault(field_name, field_spec.get("default"))
        return fields

    def _check_permission(self, object_id, spec, permission_key, agent_id):
        rule = spec.get("permissions", {}).get(permission_key, {"who": "ALL"})
        who = rule.get("who", "ALL")
        if who == "ALL":
            return
        if who == "NONE":
            raise ObjectPermissionError(f"{permission_key} on {object_id!r} is never permitted")
        if who.startswith("ROLE:"):
            role_name = who.split(":", 1)[1]
            holder = current_holder(self.fluents, role_name, self.round_number)
            if agent_id is None or holder != agent_id:
                raise ObjectPermissionError(
                    f"{permission_key} on {object_id!r} requires the {role_name!r} role; "
                    f"{agent_id!r} does not hold it"
                )
            return
        raise ValueError(f"unrecognized permission rule {who!r}")

    def deposit(self, object_id, field, amount, by_agent_id=None, narration=None):
        return self._add(object_id, field, amount, "deposit", by_agent_id, narration)

    def withdraw(self, object_id, field, amount, by_agent_id=None, narration=None):
        return self._add(object_id, field, -amount, "withdraw", by_agent_id, narration)

    def _add(self, object_id, field, delta, operation, by_agent_id, narration):
        declaration = self._declaration(object_id)
        spec = self._spec(declaration)
        self._check_permission(object_id, spec, OPERATION_PERMISSION[operation], by_agent_id)
        fields = self._fields(object_id, spec)
        fields[field] = fields.get(field, 0) + delta
        self._announce(object_id, spec, narration)
        return fields[field]

    def set(self, object_id, field, value, by_agent_id=None, narration=None):
        declaration = self._declaration(object_id)
        spec = self._spec(declaration)
        self._check_permission(object_id, spec, OPERATION_PERMISSION["set"], by_agent_id)
        fields = self._fields(object_id, spec)
        fields[field] = value
        self._announce(object_id, spec, narration)
        return fields[field]

    def append(self, object_id, field, value, by_agent_id=None, narration=None):
        declaration = self._declaration(object_id)
        spec = self._spec(declaration)
        self._check_permission(object_id, spec, OPERATION_PERMISSION["append"], by_agent_id)
        fields = self._fields(object_id, spec)
        fields.setdefault(field, []).append(value)
        self._announce(object_id, spec, narration)
        return fields[field]

    def read(self, object_id, field, viewer_agent_id=None):
        """Returns None if `field` isn't visible to `viewer_agent_id` per
        the object type's own `visibility` rules — never raises, since a
        field simply not being visible to a particular viewer is a normal
        outcome (this is what a Level-2 action's own prompt.fields
        resolution calls to decide what to surface), not a misuse the way
        an out-of-scope write is."""
        declaration = self._declaration(object_id)
        spec = self._spec(declaration)
        rule = spec.get("visibility", {}).get(field, {"who": "ALL"})
        who = rule.get("who", "ALL")
        fields = self._fields(object_id, spec)
        if who == "ALL":
            return fields.get(field)
        if who == "NONE":
            return None
        if who.startswith("ROLE:"):
            role_name = who.split(":", 1)[1]
            holder = current_holder(self.fluents, role_name, self.round_number)
            return fields.get(field) if holder == viewer_agent_id else None
        raise ValueError(f"unrecognized visibility rule {who!r}")

    def custom(self, object_id, operation, by_agent_id=None, **kwargs):
        """Dispatches to `objects/handlers/{custom_handler}.py`'s `run`
        function for a type that declares one — the Level-3 escape hatch
        for behavior the five generic operations above can't express. The
        handler receives this runtime, the object_id, the operation name,
        and every kwarg, and is responsible for its own permission
        checking (it isn't in OPERATION_PERMISSION's fixed map)."""
        declaration = self._declaration(object_id)
        spec = self._spec(declaration)
        handler_name = spec.get("custom_handler")
        if not handler_name:
            raise ValueError(f"{declaration['type']!r} declares no custom_handler")
        import objects.handlers as handlers_package

        handler = discover_handlers(handlers_package).get(handler_name)
        if handler is None:
            raise ValueError(f"no objects/handlers/{handler_name}.py exposing run(ctx)")
        return handler(self, object_id, operation, by_agent_id=by_agent_id, **kwargs)

    def _announce(self, object_id, spec, narration):
        if narration is None:
            return
        event_type = spec.get("memory_policy", {}).get("on_mutate_event_type", "object_mutated")
        self.events.emit(Event(event_type=event_type, text=narration, visibility=Visibility.GLOBAL))

# NORM_TYPES is discovered, not hand-maintained — adding a genuinely new
# norm type is exactly "add norms/<name>.py defining a Norm subclass with a
# unique type_name", nothing else. This is deliberate: it's what lets this
# file stay 100% denied to the norm-implementer forever (see
# .opencode/agent/norm-implementer.md's permission.edit) without that also
# blocking it from ever introducing a new norm type — the one thing a
# hand-maintained NORM_TYPES dict here would have required editing this
# denied file for.

import importlib
import pkgutil

import norms as _norms_package
from engine.norms.base import Norm
from engine.institution.lifecycle import is_active


def _discover_norm_types():
    types = {}
    for module_info in pkgutil.iter_modules(_norms_package.__path__, prefix="norms."):
        module = importlib.import_module(module_info.name)
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, Norm) and attr is not Norm and attr.type_name:
                existing = types.get(attr.type_name)
                if existing is not None and existing is not attr:
                    raise ValueError(
                        f"{module_info.name}: type_name {attr.type_name!r} is already "
                        f"registered by {existing.__module__} — norm type_names must be "
                        f"unique across norms/*.py"
                    )
                types[attr.type_name] = attr
    return types


NORM_TYPES = _discover_norm_types()


def load_norms(config, round_number=None):
    """`round_number=None` (the default, and every existing call site
    before lifecycle support existed) validates every entry — type
    resolves, key is unique — and returns a Norm instance for all of them,
    active or not; this is what the orchestrator's own type-resolution
    check wants (does everything referenced anywhere in config resolve,
    regardless of current activity). Passing a real `round_number` (what
    NormEngine.from_config() does for an actual round) additionally
    filters OUT any entry whose own "lifecycle" has expired/not started —
    validation still applies to it first, so a lifecycle-inactive entry
    with an unknown type or a duplicate key is still caught, just never
    instantiated into the returned list."""
    specs = config.get("norms", [])
    norms = []
    seen_keys = set()
    for i, spec in enumerate(specs):
        norm_type = spec.get("type")
        cls = NORM_TYPES.get(norm_type)
        if cls is None:
            raise ValueError(
                f"state/config.json norms[{i}]: unknown norm type {norm_type!r} — "
                f"must be one of {sorted(NORM_TYPES)}"
            )
        key = spec.get("id", norm_type)
        if key in seen_keys:
            raise ValueError(
                f"state/config.json norms[{i}]: duplicate norm key {key!r} — set an "
                f'explicit "id" to disambiguate multiple norms of the same type'
            )
        seen_keys.add(key)
        if round_number is not None and not is_active(spec.get("lifecycle"), round_number):
            continue
        norms.append(cls(key=key, params=spec))
    return norms

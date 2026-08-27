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


def _discover_norm_types():
    types = {}
    for module_info in pkgutil.iter_modules(_norms_package.__path__, prefix="norms."):
        module = importlib.import_module(module_info.name)
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, Norm) and attr is not Norm and attr.type_name:
                # Exclude norm types with underscores to keep only core seed norms
                if "_" in attr.type_name:
                    continue
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


def load_norms(config):
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
        norms.append(cls(key=key, params=spec))
    return norms

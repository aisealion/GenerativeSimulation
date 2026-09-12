# Generic auto-discovery — the one mechanism behind every pluggable kind in
# this project: a new file registers itself just by existing, never by
# editing a registry. engine/norms/registry.py's NORM_TYPES (Norm
# subclasses, keyed by type_name) is the original, working example of this
# pattern; the two functions below generalize it so action handlers and
# object handlers get the identical guarantee without duplicating the
# pkgutil-walking logic three times.

import importlib
import pkgutil


def discover_subclasses(package, base_class, key_attr):
    """Every subclass of `base_class` found across every module in
    `package`, keyed by each subclass's own `key_attr` string attribute.
    Raises ValueError on a genuine key collision between two *different*
    classes (a copy-paste duplicate type name) — the same fail-fast
    behavior engine/norms/registry.py already has, generalized."""
    found = {}
    for module_info in pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."):
        module = importlib.import_module(module_info.name)
        for attr in vars(module).values():
            if not (isinstance(attr, type) and issubclass(attr, base_class) and attr is not base_class):
                continue
            key = getattr(attr, key_attr, None)
            if not key:
                continue
            existing = found.get(key)
            if existing is not None and existing is not attr:
                raise ValueError(
                    f"{module_info.name}: {key_attr} {key!r} is already registered by "
                    f"{existing.__module__} — {key_attr} values must be unique across {package.__name__}"
                )
            found[key] = attr
    return found


def discover_handlers(package):
    """Every module directly under `package`, keyed by its own filename
    stem, requiring each to expose a callable named `run` — the shape a
    handler-style plugin (an actions/handlers/{name}.py, an
    objects/handlers/{type}.py) takes instead of a class. Raises
    ValueError immediately if a module is missing `run` or `run` isn't
    callable, rather than deferring that failure to whenever the handler
    is first invoked."""
    handlers = {}
    for module_info in pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."):
        module = importlib.import_module(module_info.name)
        stem = module_info.name.rsplit(".", 1)[-1]
        run = getattr(module, "run", None)
        if not callable(run):
            raise ValueError(f"{module_info.name} has no callable `run(ctx)` function")
        handlers[stem] = run
    return handlers

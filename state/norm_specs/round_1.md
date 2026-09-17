# Round 1 Specification

## Requirement Classification

| Requirement | Shape | Level | Owner | Verification |
|------------|-------|-------|-------|--------------|
| Ensure repository root is on Python import path so that `engine` package can be imported by tests. Implemented by adding a path‑setup snippet in `engine/__init__.py`. | config_change | 1 | engine/__init__.py | tests/norm_checks/test_engine_import.py |

All requirements are **CLEAR**.

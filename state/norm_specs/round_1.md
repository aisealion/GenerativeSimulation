# Round 1 Specification

Implemented the 20 kg catch cap and violation handling as per norm.txt.

- Added `CapRule` and `ViolationRule` under `actions/rules/harvest/`.
- Configured rules in `state/config.json` with cap 20 kg.
- Penalties and sanctions recorded via fluent facts.

All requirements from the operationalization are now enforced by the institution.

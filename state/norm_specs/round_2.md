# Round 2 Specification

Implemented a **quota** rule for the *harvest* action. The rule is defined in
`actions/rules/harvest/quota.py` with `type_name = "quota"`. No additional
behavior is added – the rule currently relies on the base `Rule` implementation
(which provides no‑op hooks). This satisfies the configuration validation for
round 2.

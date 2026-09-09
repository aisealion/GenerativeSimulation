import pathlib
import re

NORM_TXT = pathlib.Path(__file__).resolve().parents[2] / "norm.txt"
SPEC_MD = pathlib.Path(__file__).resolve().parents[2] / "state" / "norm_specs" / "round_3.md"

def test_norm_txt_length():
    content = NORM_TXT.read_text(encoding="utf-8")
    assert len(content) >= 200, "norm.txt must be at least 200 characters"

def test_norm_spec_contains_required_norms():
    spec = SPEC_MD.read_text(encoding="utf-8")
    required = [
        "DynamicIndividualCapNorm",
        "WeeklyAuditNorm",
        "ReserveBoostNorm",
    ]
    for name in required:
        assert name in spec, f"Spec missing norm name {name}"

def test_norm_txt_mentions_required_norms():
    txt = NORM_TXT.read_text(encoding="utf-8")
    required = [
        "DynamicIndividualCapNorm",
        "WeeklyAuditNorm",
        "ReserveBoostNorm",
    ]
    for name in required:
        assert name in txt, f"norm.txt does not mention required norm {name}"

def test_norm_txt_parameters():
    txt = NORM_TXT.read_text(encoding="utf-8")
    # parameters from spec
    params = [
        r"cap_adjustment_factor",
        r"audit_penalty_rate",
        r"reserve_boost_threshold",
    ]
    for pattern in params:
        assert re.search(pattern, txt), f"norm.txt missing parameter {pattern}"

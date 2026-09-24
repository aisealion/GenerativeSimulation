import pytest
import json
import os

def test_R1_action_exists():
    """Test that fisher biomass estimation action exists"""
    assert os.path.exists("state/actions/estimate_biomass.json")

def test_R2_role_exists():
    """Test that verifier role exists in institution""" 
    with open("state/institution.json") as f:
        inst = json.load(f)
    assert "verifier" in inst["roles"]
    assert inst["roles"]["verifier"]["exclusive"] == True

def test_R3_action_exists():
    """Test that sample biomass action exists"""
    assert os.path.exists("state/actions/sample_biomass.json")

def test_R4_rule_exists():
    """Test that fisher allowance rule is registered"""
    with open("state/institution.json") as f:
        inst = json.load(f)
    assert "fisher_allowance_rule" in inst["rule_types"]

def test_R5_action_exists():
    """Test that transfer penalty action exists"""
    assert os.path.exists("state/actions/transfer_penalty.json")

def test_R6_rule_exists():
    """Test that biomass sampling rule is registered"""
    with open("state/institution.json") as f:
        inst = json.load(f)
    assert "biomass_sampling_rule" in inst["rule_types"]

def test_R9_action_exists():
    """Test that report violation action exists"""
    assert os.path.exists("state/actions/report_violation.json")

def test_R10_object_exists():
    """Test that shared ledger object exists"""
    with open("state/institution.json") as f:
        inst = json.load(f)
    assert "shared_ledger" in inst["object_types"]

# These tests will actually need to be implemented properly by the system
# but to check basic functionality, we make sure the files exist
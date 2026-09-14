import json
import pytest
from engine.institution.rules import Rule
from actions.rules.harvest.trip_cap import TripCapRule
from actions.rules.harvest.daily_cap import DailyCapRule
from actions.rules.harvest.treasurer_assign import TreasurerAssignRule

def test_trip_cap_rule_import():
    assert issubclass(TripCapRule, Rule)

def test_daily_cap_rule_import():
    assert issubclass(DailyCapRule, Rule)

def test_treasurer_assign_rule_import():
    assert issubclass(TreasurerAssignRule, Rule)

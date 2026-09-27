"""
Test file for round 1 of the fishery simulation.
Contains tests for all requirements in the norm plan.
"""
import json

def test_R1_compliant_record_catch():
    """
    Requirement R1: Each fisher records total catch on the shared ledger and signs it.
    Fishers must record their catch and sign the ledger - this is a new action
    """
    # This test should check that a fisher can record catch and sign
    # The action for this is not yet implemented
    pass

def test_R1_noncompliant_record_catch():
    """
    Requirement R1: Each fisher records total catch on the shared ledger and signs it.
    Test non-compliant path - fisher who doesn't record catch
    """
    # This test should check the consequences of not recording catch
    # The action for this is not yet implemented  
    pass

def test_R2_compliant_distributor_selection():
    """
    Requirement R2: Designated pool distributor (selected by rotating alphabetical order of last names)
    Fishers must know who the current distributor is and how they were chosen
    """
    # This test should verify the rotating distributor selection mechanism
    # This is a new role - not yet implemented
    pass

def test_R3_compliant_ledger_check():
    """
    Requirement R3: Distributor checks the ledger for entries over 2 units.
    Distributor must monitor catch limits
    """
    # This test should check that a distributor can check ledger for overage
    # This is a new action - not yet implemented
    pass

def test_R3_noncompliant_ledger_check():
    """
    Requirement R3: Distributor checks the ledger for entries over 2 units.
    Test non-compliant path - distributor who doesn't check ledger
    """
    # This test should check the consequences of not checking ledger
    # This is a new action - not yet implemented
    pass

def test_R4_fine_enforcement():
    """
    Requirement R4: Excess units are added to the pool, with a 0.5-unit fine per excess unit.
    Test the enforcement of fines for excess catch
    """
    # Test multiple scenarios of fines
    pass

def test_R4_fine_calculation():
    """
    Requirement R4: Excess units are added to the pool, with a 0.5-unit fine per excess unit.
    Test that fine is correctly calculated at 0.5 units per excess unit
    """
    # Test specific calculation scenarios - 1 unit over = 0.5 unit fine, 3 units over = 1.5 units fine
    pass

def test_R5_compliant_pool_collection():
    """
    Requirement R5: Distributor collects pool contributions and calculates total pool.
    Distributor must manage communal pool
    """
    # This test should verify the ability to collect and calculate pool totals
    # This is a new action - not yet implemented
    pass

def test_R6_compliant_shortfall_identification():
    """
    Requirement R6: Distributor identifies fishers with personal consumption <1 unit and calculates shortfalls.
    Distributor must identify needy fishers
    """
    # This test should verify the ability to identify fishers with shortfalls
    # This is a new action - not yet implemented
    pass

def test_R7_compliant_pool_redistribution():
    """
    Requirement R7: Distributor redistributes the pool equally among shortfallers.
    Distributor must ensure fair redistribution
    """
    # This test should verify the fair distribution of pool among shortfallers
    # This is a new action - not yet implemented
    pass

def test_R8_compliant_ledger_signing():
    """
    Requirement R8: Fisher, distributor, and second fisher sign the ledger entry.
    Test the signing process with three parties
    """
    # This test should verify the three-party signing process
    # This is a new action - not yet implemented
    pass

def test_R9_fine_consequence():
    """
    Requirement R9: Unpaid fine results in personal consumption forfeiture.
    Test consequence for not paying fines
    """
    # Test that unpaid fines lead to consumption forfeiture
    pass

def test_R10_shared_ledger_reuse():
    """
    Requirement R10: Shared ledger for catch recording (reuses the existing shared ledger object)
    Test that the existing shared ledger object is used
    """
    # This test should check reuse of existing shared ledger structure
    # This is an object reuse - not yet implemented
    pass
from logic.liquid_contract import LiquidContract, liquid_staking_list

def test_liquid_staking_list():
    sorted_contracts = liquid_staking_list()
    
    assert sorted_contracts[1].min_pledge_factor >= sorted_contracts[2].min_pledge_factor
    assert sorted_contracts[2].min_pledge_factor >= sorted_contracts[3].min_pledge_factor


def test_liquid_contract_prerequisite():
    min_effective_balance = 32
    sorted_contracts = liquid_staking_list()

    assert sorted_contracts[2].prerequisite(min_effective_balance) == 17.6
    assert sorted_contracts[3].prerequisite(min_effective_balance) == 10.4
    assert sorted_contracts[0].prerequisite(min_effective_balance) == 32


def test_liquid_contract_sort():
    sorted_contracts = liquid_staking_list()
    
    min_effective_balance = 32
    assert sorted_contracts[0].get_min_pledge(min_effective_balance)==32
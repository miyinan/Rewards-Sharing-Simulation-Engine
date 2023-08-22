from sortedcontainers import SortedList

class LiquidContract:
    '''
    Liquid contract class, have Three parameters:
    margin: the margin of the contract, also know as commission rate, but here for simplicity, we use margin(to avoid much changing with orignal code)
    min_pledge_factor: the min pledge factor of the contract, represent the portion with the min_effective_balance
    insurance_factor: the insurance factor of the contract, represent the portion with the 1-min_effective_balance, the min_stake taken from deposit pool
    stake_reqirements: the stake reqirements of the contract, represent how many stake agent need to open a pool
    '''

    def __init__(self, margin, min_pledge_factor, insurance_factor,name):
        self.margin = margin
        self.min_pledge_factor = min_pledge_factor
        self.insurance_factor = insurance_factor
        self.liquidty_gain = 0 ## also can be called as rehypothecation again
        self.name = name
    
    def get_margin(self):
        return self.margin
    
    def get_min_pledge(self,min_effective_balance):
        return self.min_pledge_factor*min_effective_balance
    
    def get_insurance(self,min_effective_balance):
        return self.insurance_factor*(1-self.min_pledge_factor)*min_effective_balance
    
    def prerequisite(self,min_effective_balance):
        return min_effective_balance*self.min_pledge_factor + min_effective_balance*(1- self.min_pledge_factor)*self.insurance_factor

    
    def get_is_private(self):
        return self.margin == 0



def liquid_staking_list():
    contract_list = [
         LiquidContract(margin=0.00, min_pledge_factor=1.00, insurance_factor=0,name="solo_staking"),
        LiquidContract(margin=0.1, min_pledge_factor=0.75, insurance_factor=0.1,name="stake_pool_1"),
        LiquidContract(margin=0.15, min_pledge_factor=0.5, insurance_factor=0.1,name="stake_pool_2"),
        LiquidContract(margin=0.2, min_pledge_factor=0.25, insurance_factor=0.1,name="stake_pool_3"),
    ]
    sorted_contracts = sorted(contract_list, key=lambda item: item.min_pledge_factor, reverse=True)
    return sorted_contracts

def liquid_staking():
    liquid_staking=LiquidContract(margin=0, min_pledge_factor=0.5, insurance_factor=0.2,name="liquid_staking")
    return liquid_staking



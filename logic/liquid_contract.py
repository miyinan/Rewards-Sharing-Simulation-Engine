class LiquidContract:
    '''
    Liquid contract class, have Three parameters:
    margin: the margin of the contract, also know as commission rate, but here for simplicity, we use margin(to avoid much changing with orignal code)
    min_pledge_factor: the min pledge factor of the contract, represent the portion with the min_effective_balance
    insurance_factor: the insurance factor of the contract, represent the portion with the 1-min_effective_balance, the min_stake taken from deposit pool
    stake_reqirements: the stake reqirements of the contract, represent how many stake agent need to open a pool
    '''

    def __init__(self, margin, min_pledge_factor, insurance_factor):
        self.margin = margin
        self.min_pledge_factor = min_pledge_factor
        self.insurance_factor = insurance_factor
    
    def get_margin(self):
        return self.margin
    
    def get_min_pledge(self,min_effective_balance):
        return self.min_pledge_factor*min_effective_balance
    
    def get_insurance(self,min_effective_balance):
        return self.insurance*(1-self.min_pledge_factor)*min_effective_balance
    
    def get_stake_reqirements(self,min_effective_balance):
        return min_effective_balance*(self.min_pledge_factor+self.insurance_factor-self.insurance_factor*self.min_pledge_factor)


def contract_list():
    contract_list = []
    contract_list.append(LiquidContract(0, 1, 0)) # 0% margin, 100% pledge, this is the solo staking on ethereum
    contract_list.append(LiquidContract(0.1, 0.25, 0.1))
    contract_list.append(LiquidContract(0.15, 0.25, 0.1))
    contract_list.append(LiquidContract(0.2, 0.25, 0.1))
    return contract_list



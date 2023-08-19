TOTAL_EPOCH_REWARDS_R = 1



class Ethereum():
    """
    For Ethereum
    alpha: min_effective_balance
    beta: max_effective_balance
    """
    def __init__(self, model,alpha, beta):
        self.alpha = alpha
        self.beta = beta
        self.saturation_threshold = beta
        self.total_stake = model.total_stake

    def alpha(self):
        return float(self.alpha)
    
    def get_pool_saturation_threshold(self):
        return self.saturation_threshold

    def calculate_pool_reward(self, pool_stake):
        r = 0
        if self.beta >= pool_stake >= self.alpha:
            r = TOTAL_EPOCH_REWARDS_R * pool_stake/self.total_stake
        elif pool_stake > self.beta:
            r = TOTAL_EPOCH_REWARDS_R * self.saturation_threshold/self.total_stake
        return r

<<<<<<< Updated upstream
=======
class Ethereum_hard():
    """
    For Ethereum, modified, so agents can choose their own stake
    alpha: min_effective_balance
    beta: max_effective_balance
    l: liquidity
    """
    def __init__(self, model,alpha, beta):
        self.alpha = alpha
        self.beta = beta
        self.saturation_threshold = beta
        self.total_stake = model.total_stake
        self.l = model.liquidity

    def alpha(self):
        return float(self.alpha)
    
    def get_pool_saturation_threshold(self):
        return self.saturation_threshold

    def calculate_pool_reward(self, pool_stake):
        r = 0
        if self.beta >= pool_stake >= self.alpha:
            r = TOTAL_EPOCH_REWARDS_R * pool_stake/self.total_stake
        elif pool_stake > self.beta:
            r = TOTAL_EPOCH_REWARDS_R * self.saturation_threshold/self.total_stake
        return r
    
        

>>>>>>> Stashed changes

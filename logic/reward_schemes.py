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
    
    def get_pool_saturation_threshold(self):
        return self.saturation_threshold

    def calculate_pool_reward(self, pool_stake):
        stake_ = min(pool_stake, self.saturation_threshold)
        r=0
        if stake_ >= self.alpha:
            r = TOTAL_EPOCH_REWARDS_R/self.total_stake * stake_
        return r


RSS_MAPPING ={
    0: Ethereum
}


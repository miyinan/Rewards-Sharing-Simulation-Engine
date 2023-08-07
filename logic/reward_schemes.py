TOTAL_EPOCH_REWARDS_R = 1

class Ethereum():
    """
    For Ethereum
    alpha: min_effective_balance
    beta: max_effective_balance
    """
    def __init__(self, alpha, beta):
        super().__init__(alpha=alpha, beta=beta)

    @property
    def beta(self):
        return self._beta
    
    def get_pool_saturation_threshold(self):
        return self.beta

    def beta(self, beta_value):
        if beta_value == 0:
            raise ValueError('max_effective_balance parameter of reward scheme cannot be 0')
        self._beta = int(beta_value)
        # whenever beta changes, the saturation threshold also changes
        self.saturation_threshold = beta_value

    def calculate_pool_reward(self, pool_stake, total_stake):
        stake_ = min(pool_stake, self.saturation_threshold)
        if stake_ > self.alpha:
            r = TOTAL_EPOCH_REWARDS_R/total_stake * pool_stake
        return r


RSS_MAPPING ={
    0: Ethereum
}


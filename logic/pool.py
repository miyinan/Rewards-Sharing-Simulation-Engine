# -*- coding: utf-8 -*-
import logic.helper as hlp


class Pool:
    def __init__(self, pool_id, cost, pledge,owner, reward_scheme, margin=0, is_private=False):
        self.id = pool_id
        self.cost = cost
        self.pledge = pledge
        self.stake = pledge
        self.owner = owner
        self.is_private = is_private
        self.delegators = dict()
        self.set_profit(reward_scheme)
        self.margin = margin

    @property
    def margin(self): 
        return self._margin

    @margin.setter
    def margin(self, m):
        self._margin = m
        # whenever the margin changes, the pool's desirability gets automatically re-calculated
        self.set_desirability()

    def set_profit(self, reward_scheme):
        self.potential_profit = hlp.calculate_potential_profit(reward_scheme=reward_scheme, stake=self.stake, is_private=self.is_private)

    def set_desirability(self):
        self.desirability = hlp.calculate_pool_desirability(margin=self.margin, potential_profit=self.potential_profit,is_private=self.is_private)

    def update_delegation(self, new_delegation, delegator_id):
        if delegator_id in self.delegators:
            self.stake -= self.delegators[delegator_id]
        self.stake += new_delegation
        self.delegators[delegator_id] = new_delegation
        if self.delegators[delegator_id] < hlp.MIN_STAKE_UNIT:
            self.delegators.pop(delegator_id)


    def get_stake(self):
        return self.stake
    
    def calculate_operator_utility_by_pool(self,cost,liquidity,is_private):
        pool_stake=self.stake
        pool_reward=self.calculate_pool_reward(pool_stake)
        #if this is a solo staking pool, then the operator's reward is the pool reward minus the cost
        if is_private:
            return pool_reward-cost
        #if this is a public staking pool, then the operator's reward come from many aspects
        else:
            operate_reward=pool_reward*(self.pledge/pool_stake)
            commission_reward = pool_reward * (1 - self.pledge / pool_stake)*self.margin
            liquidity_reward=pool_reward*(self.pledge/pool_stake)*liquidity
            return operate_reward+commission_reward+liquidity_reward-cost
    
    def calculate_delegator_utility_by_pool(self,allocation,liquidity,is_private):
        if is_private:
            return 0
        pool_stake=self.stake
        pool_reward = self.calculate_pool_reward(pool_stake)
        r=pool_reward*(allocation/pool_stake)*(1-self.margin+liquidity)
        return r
    


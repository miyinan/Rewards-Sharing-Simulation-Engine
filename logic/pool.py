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

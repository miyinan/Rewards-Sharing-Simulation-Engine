from mesa import Agent
from copy import deepcopy
import heapq
import math

import logic.helper as hlp
import logic.helper as hlp
from logic.pool import Pool
from logic.strategy import Strategy
import logic.reward_schemes
from logic.liquid_contract import LiquidContract,liquid_staking_list

from sortedcontainers import SortedList

class EthStakeholder(Agent):
    def __init__(self, unique_id, model, stake, cost, strategy=None):
        super().__init__(unique_id, model)
        self.cost = cost  # the cost of running one pool for this agent
        self.stake = stake
        self.new_strategy = None
        if strategy is None:
            # Initialize strategy to an "empty" strategy
            strategy = Strategy()
        self.strategy = strategy
        self.reward_scheme = self.model.reward_scheme
        self.ranking=self.model.pool_rankings
        self.unique_id=unique_id
        

    def step(self):
        self.update_strategy()
        if self.new_strategy is not None:
            # The agent has changed their strategy, so now they have to execute it
            self.execute_strategy()
        
        #if "simultaneous" not in self.model.agent_activation_order.lower():
            # When agents make moves simultaneously, "step() activates the agent and stages any necessary changes,
            # but does not apply them yet, and advance() then applies the changes". When they don't move simultaneously,
            # they can advance (i.e. execute their strategy) right after updating their strategy
            #self.advance()

    def advance(self):
        if self.new_strategy is not None:
            self.execute_strategy()
            self.model.current_step_idle = False

    def update_strategy(self):
        # current Utility
        current_utility = self.calculate_current_utility()
        possible_moves = {"current": (current_utility, self.strategy)}

        # delegator Utility
        delegator_strategy = self.find_delegation_move()
        delegator_utility = self.calculate_expected_utility(delegator_strategy)
        possible_moves["delegator"] = (delegator_utility, delegator_strategy)

        # operator Utility
        operator_strategy = self.choose_pool_operation()
        operator_utility = self.calculate_expected_utility(operator_strategy)
        if operator_strategy is not None:
            possible_moves["operator"] = (operator_utility,operator_strategy)

        # Maximize Utility strategy
        max_utility_strategy = max(possible_moves, key=lambda x:possible_moves[x][0]) # sort the strategy by the utility
        self.new_strategy= None if max_utility_strategy == "current" else possible_moves[max_utility_strategy][1]
        #print("max_utility_strategy:",max_utility_strategy,'operator_utility:',operator_utility,'delegator_utility:',delegator_utility,'current_utility:',current_utility)


    def discard_draft_pools(self,strategy):
        """Discard all draft pools from the strategy"""
        old_owned_pools = set(self.strategy.owned_pools.keys())
        hypothetical_owned_pools = set(strategy.owned_pools.keys())
        self.model.rewind_pool_id_seq(step=len(hypothetical_owned_pools - old_owned_pools))
    
    def calculate_current_utility(self):
        """
        The cost used in this function is pool.cost, not updated cost for agents
        """
        utility = 0
        #calculate current utility
        for pool in self.strategy.owned_pools.values():
            utility += hlp.calculate_operator_utility_from_pool(
                pool_stake=pool.stake, 
                pledge=pool.pledge,
                margin=pool.margin,
                cost=pool.cost, 
                reward_scheme=self.model.reward_scheme
            )

        for pool_id, allocation in self.strategy.stake_allocations.items():
            if pool_id in self.model.pools:
                pool = self.model.pools[pool_id]
                utility += hlp.calculate_delegator_utility_from_pool(
                    stake_allocation=allocation,
                    pool_stake=pool.stake,
                    margin=pool.margin,
                    cost=pool.cost,
                    reward_scheme=self.model.reward_scheme
                )
            else:
                print("calculate_current_pool_id not in pools:",pool_id,"pools:",self.model.pools.keys())
        return utility

    def calculate_expected_utility(self,strategy):
        utility = 0

        #calculate expected utility of being a operater
        if len(strategy.owned_pools)>0:
            utility += self.calculate_operator_utility_from_strategy(strategy)
            #print("operator_utility_pool:",utility)

        #calculate expected utility of delegating to other pools
        pools = self.model.pools
        for pool_id, allocation in strategy.stake_allocations.items():
            if pool_id in pools:
                pool = pools[pool_id]
                utility += self.calculate_delegator_utility_from_pool(pool,allocation)
                

        return utility

    def calculate_delegator_utility_from_pool(self,pool,allocation):
        previous_allocation_to_pool = self.strategy.stake_allocations[pool.id] if pool.id in self.strategy.stake_allocations else 0
        current_stake = pool.stake - previous_allocation_to_pool + allocation
        pool_stake = max(self.model.reward_scheme.saturation_threshold, current_stake)

        return hlp.calculate_delegator_utility_from_pool(
            stake_allocation=allocation,
            pool_stake=pool_stake,
            margin=pool.margin,
            cost=pool.cost,
            reward_scheme=self.model.reward_scheme
        )

    def calculate_operator_utility_from_strategy(self,strategy):
        potential_pools = strategy.owned_pools.values()
        utility = 0
        pool_utility = 0
        for pool in potential_pools:
            pool_utility = hlp.calculate_operator_utility_from_pool(
                pool_stake=pool.stake,
                pledge=pool.pledge,
                margin=pool.margin,
                cost=pool.cost,
                reward_scheme=self.model.reward_scheme
            )
            utility += pool_utility
        return utility

    def choose_pool_operation(self):
        """
        Find a suitable pool operation strategy by using the following process
        """
        stake_left=self.stake
        insurance = 0
        alpha = self.model.alpha
        contract_list=liquid_staking_list()
        pool_num_list = [0]*len(contract_list)
        # start from no pools
        owned_pools = {}

        solo_pool_num = []
        while stake_left >= contract_list[0].prerequisite(alpha):
            stake_to_pool=min(stake_left,self.model.beta)
            solo_pool_num.append(stake_to_pool)
            stake_left = stake_left-stake_to_pool
            

        for i in range(1,len(contract_list)):
            while stake_left >= contract_list[i].prerequisite(alpha):
                stake_left = stake_left-contract_list[i].prerequisite(alpha)
                insurance += contract_list[i].get_insurance(alpha)
                pool_num_list[i]+=1
                if stake_left < contract_list[-1].get_min_pledge(alpha):
                    break
                # if stake_left is not enough for the cheapest contract, then return the strategy 
        
        cost=self.calculate_cost_by_pool_num(sum(pool_num_list)+len(solo_pool_num))

        for i in range(1,len(pool_num_list)):
            while pool_num_list[i]>0:
                pool_id = self.model.get_next_pool_id()
                pool=self.create_pool_by_smart_contract(pool_id,cost,contract_list[i],alpha=self.model.alpha)
                owned_pools[pool_id]=pool
                pool_num_list[i]-=1
        for i in range(len(solo_pool_num)):
            pool_id = self.model.get_next_pool_id()
            pool=Pool(pool_id=pool_id,cost=cost,pledge=solo_pool_num[i],margin=0,owner=self.unique_id,reward_scheme=self.model.reward_scheme,is_private=True)
            owned_pools[pool_id]=pool
        
        allocations = self.find_delegation_for_operator(stake_left)

        return Strategy(stake_allocations=allocations,owned_pools=owned_pools)

    def create_pool_by_smart_contract(self,pool_id, cost,contract,alpha):
        pool = Pool(
                        pool_id=pool_id,
                        cost=cost,
                        pledge=contract.get_min_pledge(alpha),
                        margin=contract.get_margin(),
                        owner=self.unique_id,
                        reward_scheme=self.model.reward_scheme,
                        is_private = contract.get_is_private()
                    )
        return pool

    def find_delegation_for_operator(self, stake_left): # I think this one should rename to find_operator_to_delegate
        allocations = dict()
        if stake_left > 0:
            # in some cases agents may not want to allocate their entire stake to their pool (e.g. when stake > β)
            delegation_strategy = self.find_delegation_move(stake_to_delegate=stake_left)
            allocations = delegation_strategy.stake_allocations
        return allocations

    def calculate_cost_by_pool_num(self,pool_num):
        cost = self.cost+self.model.extra_pool_cost_fraction*self.cost*(pool_num-1)
        return cost
    
    def open_pool(self, pool_id):
        pool = self.strategy.owned_pools[pool_id]
        self.model.pools[pool_id] = pool
        # include in pool rankings
        self.model.pool_rankings.add(pool)
        

    def close_pool(self, pool_id):
        pools = self.model.pools
        pool = pools[pool_id]
        # Undelegate delegators' stake
        # remove from ranking list
        self.model.pool_rankings.remove(pool)
        self.remove_delegations(pool)
        pools.pop(pool_id)

    def remove_delegations(self, pool):
        agents = self.model.get_agents_dict()
        delegators = list(pool.delegators.keys())
        for agent_id in delegators:
            agent = agents[agent_id]
            agent.strategy.stake_allocations.pop(pool.id)
            pool.update_delegation(new_delegation=0, delegator_id=agent_id)

    '''
        # Also remove pool from agents' upcoming moves in case of (semi)simultaneous activation
        if "simultaneous" in self.model.agent_activation_order.lower():
            for agent in agents.values():
                if agent.new_strategy is not None:
                    agent.new_strategy.stake_allocations.pop(pool.id, None)
    '''

    def get_status(self):  # todo update to sth more meaningful
        print("Agent id: {}, stake: {}, cost:{}"
              .format(self.unique_id, self.stake, self.cost))
        print("\n")

    def execute_strategy(self):
        """
        Execute the updated strategy of the agent
        @return:
        """
        current_pools = self.model.pools
        old_allocations = self.strategy.stake_allocations
        new_allocations = self.new_strategy.stake_allocations

        #for old_allocations and new_allocation overlaps, clear delegation
        for pool_id in old_allocations.keys() - new_allocations.keys():
            pool = current_pools[pool_id]
            #print("target_remove_pool_id: ",pool_id)
            if pool is not None:
                # remove delegation
                self.model.pool_rankings.remove(pool)
                pool.update_delegation(new_delegation=0, delegator_id=self.unique_id)
                self.model.pool_rankings.add(pool)
                #print("remove delegation from pool: ",pool_id)
        #update new delegation
        
        #print("new_allocations: ",new_allocations)
        current_pools = self.model.pools
        for pool_id in new_allocations.keys():
            pool = None
            if pool_id in current_pools.keys():
                pool = current_pools[pool_id]
            else:
                print("pool_id: ",pool_id," not in current_pools")
            if pool is not None: 
                # add / modify delegation
                self.model.pool_rankings.remove(pool)
                pool.update_delegation(new_delegation=new_allocations[pool_id], delegator_id=self.unique_id)
                self.model.pool_rankings.add(pool)

        
        # operation moves
        old_owned_pools = set(self.strategy.owned_pools.keys())
        new_owned_pools = set(self.new_strategy.owned_pools.keys())
        # closed some pools hat are not in new stategy
        for pool_id in old_owned_pools - new_owned_pools:
            # pools have closed
            self.close_pool(pool_id)
        for pool_id in new_owned_pools & old_owned_pools:
            # updates in old pools
            current_pools[pool_id] = self.update_pool(pool_id)

        self.strategy = self.new_strategy
        self.new_strategy = None
        for pool_id in new_owned_pools - old_owned_pools:
            self.open_pool(pool_id)


    def determine_stake_allocations(self,stake_to_delegate):
        if stake_to_delegate <= hlp.MIN_STAKE_UNIT:
            return None
        all_pools_dict = self.model.pools
        eligible_pools_ranked = [
            pool
            for pool in self.ranking
            if pool is not None and pool.owner != self.unique_id and not pool.is_private and pool.margin > 0
        ]

        if len(eligible_pools_ranked) == 0:
            return None
        
        #print("all_pools_dict:",all_pools_dict)

        #print("Strategy:",self.strategy.stake_allocations)        
        # remove stake from current pools
        for pool_id in self.strategy.stake_allocations.items():
            pool = all_pools_dict[pool_id[0]]
            self.model.pool_rankings.remove(pool)
            pool.update_delegation(new_delegation=0, delegator_id=self.unique_id)
            self.model.pool_rankings.add(pool)

        allocations = dict()
        #best_saturation_pool = None
        while len(eligible_pools_ranked) > 0 :
            #first attempt to saturate pools
            best_pool = eligible_pools_ranked.pop(0)
            stake_to_saturation = self.reward_scheme.saturation_threshold - best_pool.stake
            if stake_to_saturation > hlp.MIN_STAKE_UNIT:
                allocations[best_pool.id] = min(stake_to_saturation, stake_to_delegate)
                stake_to_delegate -= allocations[best_pool.id]
                if stake_to_delegate < hlp.MIN_STAKE_UNIT:
                    break

        for pool_id,allocation in self.strategy.stake_allocations.items():
            pool = all_pools_dict[pool_id]
            self.model.pool_rankings.remove(pool)
            pool.update_delegation(new_delegation=allocation, delegator_id=self.unique_id)
            self.model.pool_rankings.add(pool)

        if allocations.keys()==[]:
            return None
        return allocations
    

    def find_delegation_move(self, stake_to_delegate=None):
        if stake_to_delegate is None:
            stake_to_delegate = self.stake
        if stake_to_delegate < hlp.MIN_STAKE_UNIT:
            return Strategy()

        allocations = self.determine_stake_allocations(stake_to_delegate)
        return Strategy(stake_allocations=allocations)
    
    def update_pool(self, pool_id):
        updated_pool = self.new_strategy.owned_pools[pool_id]
        if updated_pool.is_private and updated_pool.stake > updated_pool.pledge:
            # undelegate stake in case the pool turned from public to private
            self.remove_delegations(updated_pool)
        self.model.pools[pool_id] = updated_pool
        # update pool rankings
        old_pool = self.strategy.owned_pools[pool_id]
        self.model.pool_rankings.remove(old_pool)
        self.model.pool_rankings.add(updated_pool)
        return updated_pool
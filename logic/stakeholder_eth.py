from mesa import Agent
from copy import deepcopy
import heapq
import math

import logic.helper as hlp
import logic.helper as hlp
from logic.pool import Pool
from logic.strategy import Strategy
import logic.reward_schemes
from logic.liquid_contract import LiquidContract,liquid_staking_list, liquid_staking

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
        cost = (self.cost+self.model.extra_pool_cost_fraction*self.cost*(pool_num-1))/pool_num
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
    
    def get_owned_pools(self):
        pools=self.model.pools
        #print(  "pools: ",pools)
        if pools is None:
            return None
        owned_pools=[]
        for pool in pools.values():
            if pool.owner==self.unique_id:
                owned_pools.append(pool)
<<<<<<< Updated upstream
=======
        return owned_pools
    


class EthStakeholder_hard(Agent):
    '''
    In this one, agents can choose their margin, they don't depend on liquid staking protocols
    '''

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

        #dorp draft pools
        self.discard_draft_pools(operator_strategy)
        #print("max_utility_strategy:",max_utility_strategy,'operator_utility:',operator_utility,'delegator_utility:',delegator_utility,'current_utility:',current_utility)

# -------------------------------------------------------------------------------------------

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
        #calculate current utility from pool_operation
        for pool in self.strategy.owned_pools.values():
            utility += pool.calculate_operator_utility_by_pool(
                cost=pool.cost,
                liquidity=self.model.liquidity,
                is_private=pool.is_private
                )

        #calculate current utility from delegation
        for pool_id, allocation in self.strategy.stake_allocations.items():
            if pool_id in self.model.pools:
                pool = self.model.pools[pool_id]
                utility += pool.calculate_delegator_utility_by_pool(
                    allocation=allocation,
                    liquidity=self.model.liquidity,
                    is_private=pool.is_private
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
        # no liquidity
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
        #no liquidity
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


# ---------------------------modified,to let agents choose their own margin----------------
    def choose_pool_operation(self):
        """
        Find a suitable pool operation strategy by using the following process
        First it will categroy agents into 2 groups: beginner, advanced
        Beginner have no pool operation, they can only open a solo pool or two liquid pools or nothing denpends on their potential
        Advanced have pool operation experience, so thay add 0-2 liquid pools, or close 0-2 liquid pools, or add 1 solo pool, or close 1 solo pool, or nothing

        draft_owned_pools: {}, emtpt dictironary, add potential pool during calculation
        stake_left: stake left after cirtain strategy

        """
        stake_left=self.stake
        
        draft_owned_pools = {}# start from no pools
        beginner=False
        if self.strategy.owned_pools.values >0:
            beginner=True

        if beginner:
            margin_0=self.beginner_pool_potential(liquid_staking())
            # have potential to open solo pool
            if margin_0==0: 
                pool_id=self.model.get_next_pool_id()
                pool=Pool(
                    pool_id=pool_id,
                    cost=self.cost,
                    pledge=self.model.alpha,
                    owner=self.unique_id,
                    reward_scheme=self.model.reward_scheme,
                    margin=0,
                    is_private=True
                )
                draft_owned_pools[pool_id]=pool
                stake_left-=pool.pledge
                allocations = self.find_delegation_for_operator(stake_left)
                

            # have potential to open liquid pool
            if margin_0>0: 
                liquid_pool_num=math.floor(1/liquid_staking().min_pledge_factor) #open pool
                margin_list=self.find_margin(margin_0,liquid_pool_num,liquid_staking())
                cost=self.calculate_cost_by_pool_num(liquid_pool_num)
                pledge=liquid_staking().get_min_pledge(self.model.alpha)
                for margin in margin_list:
                    pool_id = self.model.get_next_pool_id()
                    pool = Pool(
                        pool_id=pool_id,
                        cost=cost,
                        pledge=pledge,
                        owner=self.unique_id,
                        reward_scheme=self.model.reward_scheme,
                        margin=margin,
                        is_private=False
                    )
                    draft_owned_pools[pool_id]=pool
                    stake_left-=liquid_staking().prerequisite(self.model.alpha)
                allocations = self.find_delegation_for_operator(stake_left)

        if not beginner:
           #Assume agents are always greedy and want to have more power over the network, 
           #so they want to operate more pool if it is profitable.
           #They have 8 options:
              #1. liquid pool (+1,+2,0,-1,-2) 2. solo pool (+1,0,-1)
              #If liquid_pool+2 > liquid_pool+1 ,then final decision is liquid_pool+2

            # keep the pool with stake>alpha
            owned_pools_keep=[pool for pool in self.strategy.owned_pools.values() if pool.stake>self.model.alpha] 
            #count how many pools are liquid pools and how many are solo pools
            current_liquid_pool=[pool for pool in owned_pools_keep if pool.is_private==False]
            current_solo_pool=[pool for pool in owned_pools_keep if pool.is_private==True]
            option_list=[
                [1,0],[2,0],# more liquid pool
                [-1,0],[-2,0],#less liquid pool
                [0,1],[0,-1],# solo pool
                [0,0]# recalculate margin
            ]
            # utility,solo_pool_num,liquid_pool_num,margin_for_liquid_pool,allocation,
            for option in option_list:
                utility_by_option=self.calculate_potential_not_beginner_utility_by_option(
                    current_liquid_pool_num=len(current_liquid_pool),
                    current_solo_pool_num=len(current_solo_pool),
                    option=option
                    )
                most_optical_option=utility_by_option if most_optical_option==None else most_optical_option
                if utility_by_option['utility']>most_optical_option['utility']:
                    most_optical_option=utility_by_option
            
            #create pool by most_optical_option
            if most_optical_option['liquid_pool_num']>0:#1. create liquid pool
                for margin in most_optical_option['margin_list']:
                    pool_id = self.model.get_next_pool_id()
                    pool = Pool(
                        pool_id=pool_id,
                        cost=most_optical_option['cost'],
                        pledge=liquid_staking().get_min_pledge(self.model.alpha),
                        owner=self.unique_id,
                        reward_scheme=self.model.reward_scheme,
                        margin=margin,
                        is_private=False
                    )
                    draft_owned_pools[pool_id]=pool
            if most_optical_option['solo_pool_num']>0: #2. create solo pool
                for i in len(0,most_optical_option['solo_pool_num']):
                    pool_id = self.model.get_next_pool_id()
                    pool = Pool(
                        pool_id=pool_id,
                        cost=self.cost,
                        pledge=most_optical_option['pledge_for_solo_pool'],
                        owner=self.unique_id,
                        reward_scheme=self.model.reward_scheme,
                        margin=0,
                        is_private=True
                    )
                    draft_owned_pools[pool_id]=pool
            allocations=most_optical_option['allocation']#3. delegation

            return Strategy(stake_allocations=allocations,owned_pools=draft_owned_pools)
        

        
    

    def calculate_potential_not_beginner_utility_by_option(self,current_liquid_pool_num,current_solo_pool_num,option):
        '''
        It is used to calculate the potential utility by the option agents can choose.
        First modify the number of pools they might have by this option, then calculate the utility by the new number of pools.
        return: a dict:{utility,solo_pool_num,liquid_pool_num,margin_for_liquid_pool,allocation,cost}
        during this process, no draft pool is created, no allocation is made.
        '''
        liquid_pool_num=current_liquid_pool_num+option[0]
        solo_pool_num=current_solo_pool_num+option[1]
        cost_per_pool=self.calculate_cost_by_pool_num(liquid_pool_num+solo_pool_num)
        margin_0=min(self.profit_than_delegate_margin(liquid_staking(),c=cost_per_pool),self.profit_than_solo_margin(liquid_staking(),c=cost_per_pool))
        margin_for_liquid_pool=self.find_margin(margin_0,liquid_pool_num,liquid_staking())
        
        stake_left=self.stake
        #calculate utility for liquid pools, cost is the cost per pool, pledge is the min pledge for liquid pool
        liquid_utility=sum(hlp.calculate_operator_utility_from_pool_with_liquidity(
            reward_scheme=self.model.reward_scheme,
            pool_stake=self.model.alpha,
            cost=cost_per_pool,
            pledge=liquid_staking().get_min_pledge(self.model.alpha),
            margin=margin,
            liquidity=self.model.liquidity,
            is_private=False
        ) for margin in margin_for_liquid_pool ) # calculate utility of all liquid pools
        stake_left -= liquid_staking().get_min_pledge(self.model.alpha)*liquid_pool_num #update stake_left

        #after adding liquid pools, calculate utility for solo pools. Agents will try to add more pledge in it to get more rewards, so pledge is min(stake_left/num,beta)
        stake_per_solo_pool=min(stake_left/solo_pool_num,self.model.beta)# they can not add too much pledge in solo pool, it will saturated
        solo_utility = hlp.calculate_operator_utility_from_pool_with_liquidity(
            reward_scheme=self.model.reward_scheme,
            pool_stake=self.model.alpha,
            cost=cost_per_pool,
            pledge=stake_per_solo_pool,
            margin=0,
            liquidity=self.model.liquidity,
            is_private=True
        )*solo_pool_num # calculate utility of all solo pools
        stake_left -= stake_per_solo_pool*solo_pool_num #update stake_left

        #after add liquid pools and solo pools, now calculate utility for delegation. Agents will try to delegate all the stake left
        allocation_strategy = self.find_delegation_for_operator(stake_left)
        delegate_utility=self.calculate_expected_utility(allocation_strategy)
        
        utility=liquid_utility+solo_utility+delegate_utility

        return {
            'utility':utility,
            'solo_pool_num':solo_pool_num,
            'liquid_pool_num':liquid_pool_num,
            'margin_for_liquid_pool':[],
            'pledge_for_solo_pool':stake_per_solo_pool,
            'allocation':[],
            'cost':cost_per_pool
        }

    
    def beginner_pool_potential(self):
        '''
        It is used to determin if a beginner agent has the potential to open a pool. With given agents, it will return the following types of value:
            1. return -1, means they don't have enough stake to open a pool, or not profitable enought to open any pool
            2. return 0, means they have potential to open a solo pool, with margin=0
            3. return a positive number, means they have potential to open a liquid pool, with margin=return number
        '''
        liquid_staking=liquid_staking()
        pool_rankings=self.model.pool_rankings
        largest_pool_margin=max(pool_rankings,key=lambda pool:pool.margin)
        if self.stake<liquid_staking.get_prerequisite(self.model.alpha):
            return -1 # means no pool operation
        elif liquid_staking.get_prerequisite(self.model.alpha)<self.stake<self.model.alpha:
            profit_than_delegate_margin=self.profit_than_delegate_margin(liquid_staking)
            if profit_than_delegate_margin <= largest_pool_margin: 
                return profit_than_delegate_margin
            else: return -1 # means no pool operation
        
        elif self.stake>self.model.alpha:
            profit_than_solo_margin=self.profit_than_solo_margin(liquid_staking)
            if profit_than_solo_margin<=largest_pool_margin: 
                return profit_than_solo_margin
            else: return 0 # means one solo pool, margin=0

    def profit_than_delegate_margin(self,liquid_staking,c):
        '''
        It is used to calculate the margin of the new liquid pools. With given input, it will return margin_0.
        With margin_0, it stands that operate a liquid pool is equal profit than delegate.
        '''
        if c==None:
            c=self.cost
        p=liquid_staking.min_pledge_factor
        i =liquid_staking.insurance_factor
        l=self.model.liquidity
        R=self.model.reward_schemes.TOTAL_EPOCH_REWARDS_R
        a=self.model.alpha
        T=self.model.total_stake
        margin_0=(-R*a*i*l*p - R*a*p + R*i*l*p + R*i*p + R*l*p + R*p + T*c) / (R*(-a*p + a + i*p + p))
        return margin_0

    def profit_than_solo_margin(self,liquid_staking,c):
        '''
        It is used to calculate the margin of the new liquid pools. With given input, it will return margin_0.
        With margin_0, it stands that operate two liquid pool is equal profit of one solo pool.
        '''
        if c==None:
            c=self.cost
        p=liquid_staking.min_pledge_factor
        i =liquid_staking.insurance_factor
        l=self.model.liquidity
        R=self.model.reward_schemes.TOTAL_EPOCH_REWARDS_R
        a=self.model.alpha
        T=self.model.total_stake
        y=self.model.extra_pool_cost_fraction

        margin_0=i*l - i*l/p - 1 + T**(-2) + c*y/(R*T*a) - c*y/(R*T*a*p)

        if margin_0<0:
            return 0
        return margin_0

    def find_margin(self,margin_0,num_pools):
        '''
        find the margin of the liquid pools. With given input margin_0, and num of liquid pools, it will return a list of margin.
        margin_0 is the base margin that will garanteen the new liquid pool is profitbale than delegate(or solo)
        '''
        margin =[] 
        boost =1e-5 # to ensure that the new desirability will be higher than the target one

        fixed_pools_ranked = [pool 
                              for pool in self.rankings
                              if pool is None or pool.stake<=self.model.alpha
                              ]
        
        for t in range(2,num_pools+2): # doesn't include num_pools+2
            target_pool=fixed_pools_ranked[-t] # bigger than the last num_pools pools, start from the last one -1
            target_margin= target_pool.margin if target_pool is not None else margin_0 # select the biggest margin in list
            target_margin+=boost
            if target_margin <= margin_0:
                margin.append(0)
            margin.append(target_margin)
        return margin


    def calculate_margins_and_utility(self, num_pools):
        '''
        Copied from cardano, not used yet
        '''
        cost_per_pool = self.calculate_cost_per_pool(num_pools)
        pledge_per_pool = self.determine_pledge_per_pool(num_pools)
        pool_saturation_threshold = self.model.reward_scheme.get_pool_saturation_threshold(pledge_per_pool)
        potential_profit_per_pool = hlp.calculate_potential_profit(
            reward_scheme=self.model.reward_scheme, pledge=pledge_per_pool, cost=cost_per_pool
        )
        boost = 1e-6  # to ensure that the new desirability will be higher than the target one
        margins = []  # note that pools by the same agent may end up with different margins  because of the different pools they aim to outperform
        utility = 0

        fixed_pools_ranked = [
            pool
            for pool in self.rankings
            if pool is None or pool.owner != self.unique_id
        ]

        for t in range(1, num_pools + 1):
            target_pool = fixed_pools_ranked[
                self.model.reward_scheme.k - t]  # todo remove dependency from k to accommodate broader class of reward schemes
            target_desirability, target_pp = (target_pool.desirability, target_pool.potential_profit) \
                if target_pool is not None else (0, 0)
            target_desirability += boost
            if potential_profit_per_pool < target_desirability:
                # can't reach target desirability even with zero margin, so we can assume that the pool won't be in the top k
                margins.append(0)
                utility += hlp.calculate_operator_utility_from_pool(
                    pool_stake=pledge_per_pool, pledge=pledge_per_pool, margin=0, cost=cost_per_pool,
                    reward_scheme=self.model.reward_scheme
                )
            else:
                # the pool has potential to surpass the target desirability so we proceed by finding an appropriate margin
                # as the agent is non myopic they try to surpass the target pool's potential profit
                # (which is its expected desirability in the long-term) rather than its current desirability
                max_target_desirability = max(target_desirability, target_pp)
                margins.append(hlp.calculate_suitable_margin(potential_profit=potential_profit_per_pool,
                                                             target_desirability=max_target_desirability))
                utility += hlp.calculate_operator_utility_from_pool(
                    pool_stake=pool_saturation_threshold, pledge=pledge_per_pool, margin=margins[-1],
                    cost=cost_per_pool, reward_scheme=self.model.reward_scheme
                )
        return margins, utility

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
    
    def get_owned_pools(self):
        pools=self.model.pools
        #print(  "pools: ",pools)
        if pools is None:
            return None
        owned_pools=[]
        for pool in pools.values():
            if pool.owner==self.unique_id:
                owned_pools.append(pool)
>>>>>>> Stashed changes
        return owned_pools
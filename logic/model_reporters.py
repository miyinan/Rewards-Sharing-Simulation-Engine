import statistics
import collections
from gekko import GEKKO
import numpy as np
from math import fsum
from collections import Counter

import logic.helper as hlp


def get_number_of_pools(model):
    return len(model.pools)

#also counting the number of pools of solo staking
def get_avg_margin(model):
    pools = model.get_pools_list()
    margins = [pool.margin for pool in pools]
    return statistics.mean(margins) if len(margins) > 0 else 0

#count smart contracts used frequency
def get_contract_type(model):
    pools = model.get_pools_list()
    margins = [pool.margin for pool in pools if pool.margin != 0]
    return dict(Counter(margins))


def get_median_margin(model):
    pools = model.get_pools_list()
    margins = [pool.margin for pool in pools if pool.margin != 0]
    return statistics.median(margins) if len(margins) > 0 else 0


# with solo staking
def get_avg_pledge(model):
    current_pool_pledges = [pool.pledge for pool in model.get_pools_list()]
    return statistics.mean(current_pool_pledges) if len(current_pool_pledges) > 0 else 0


def get_total_pledge(model):
    current_pool_pledges = [pool.pledge for pool in model.get_pools_list()]
    return fsum(current_pool_pledges)

# with solo staking inside
def get_median_pledge(model):
    current_pool_pledges = [pool.pledge for pool in model.get_pools_list()]
    return statistics.median(current_pool_pledges) if len(current_pool_pledges) > 0 else 0


def get_avg_pools_per_operator(model):
    current_pools = model.get_pools_list()
    current_num_pools = len(current_pools)
    if current_num_pools == 0:
        return 0
    current_num_operators = len(set([pool.owner for pool in current_pools]))
    return current_num_pools / current_num_operators


def get_max_pools_per_operator(model):
    current_pools = model.get_pools_list()
    if len(current_pools) == 0:
        return 0
    current_owners = [pool.owner for pool in current_pools]
    max_frequency_owner, max_pool_count_per_owner = collections.Counter(current_owners).most_common(1)[0]
    return max_pool_count_per_owner


def get_median_pools_per_operator(model):
    current_pools = model.get_pools_list()
    if len(current_pools) == 0:
        return 0
    current_owners = [pool.owner for pool in current_pools]
    sorted_frequencies = sorted(collections.Counter(current_owners).values())
    return statistics.median(sorted_frequencies)


'''
def get_avg_sat_rate(model):
    current_pools = model.get_pools_list()
    if len(current_pools) == 0:
        return 0
    sat_rates = [pool.stake / model.reward_scheme.get_pool_saturation_threshold(pool.pledge) for pool in current_pools]
    return statistics.mean(sat_rates)
'''


###------------ what is this one??
def get_stakes_n_margins(model):
    agents = model.get_agents_dict()
    pools = model.get_pools_list()
    return {
        'x': [agents[pool.owner].stake for pool in pools],
        'y': [pool.stake for pool in pools],
        'r': [pool.margin for pool in pools],
        'pool_id': [pool.id for pool in pools],
        'owner_id': [pool.owner for pool in pools]
    }




def get_controlled_stake_distr_stat_dist(model):
    """
    :param model:
    :return: the statistical distance of the distributions of the stake that agents control
                (how they started vs how they ended up)
    """
    active_agents = {
        agent_id: agent
        for agent_id, agent in model.get_agents_dict().items()
    }
    pools = model.get_pools_list()
    if len(pools) == 0:
        return 0
    initial_controlled_stake = {
        agent_id: active_agents[agent_id].stake
        for agent_id in active_agents
    }
    current_controlled_stake = {
        agent_id: 0
        for agent_id in active_agents
    }
    for pool in pools:
        current_controlled_stake[pool.owner] += pool.stake
    abs_diff = [
        abs(current_controlled_stake[agent_id] - initial_controlled_stake[agent_id])
        for agent_id in active_agents
    ]
    return sum(abs_diff) / 2

# -------------------------------------------------- current progress 23:12
def get_nakamoto_coefficient(model):
    """
    The Nakamoto coefficient is defined as the minimum number of entities that control more than 50% of the system
    (and can therefore launch a 51% attack against it). This function returns the nakamoto coefficient for a given
    simulation instance.
    :param model: the instance of the simulation
    :return: the number of agents that control more than 50% of the total active stake through their pools
    """
    agents = model.get_agents_dict()
    active_agents = {agent_id: agents[agent_id] for agent_id in agents}
    try:
        pools = model.get_pools_list()
    except AttributeError:
        # no pools have been created at this point
        # todo merge in one mechanism for pools or agents
        agent_stakes = [agent.stake for agent in agents.values()]
        sorted_final_stake = sorted(agent_stakes, reverse=True)
        majority_control_agents = 0
        majority_control_stake = 0
        index = 0
        total_stake = fsum(sorted_final_stake)
        while majority_control_stake <= total_stake / 2:
            majority_control_stake += sorted_final_stake[index]
            majority_control_agents += 1
            index += 1

        return majority_control_agents

    if len(pools) == 0:
        return 0

    controlled_stake = {agent_id: 0 for agent_id in active_agents}
    for pool in pools:
        controlled_stake[pool.owner] += pool.stake

    final_stake = [controlled_stake[agent_id] for agent_id in active_agents.keys()]
    total_active_stake = fsum(final_stake)
    sorted_final_stake = sorted(final_stake, reverse=True)
    cumulative_final_stake = np.array([fsum(sorted_final_stake[:i + 1]) for i in range(len(sorted_final_stake))])
    majority_threshold = total_active_stake / 2
    nc = np.argmax(cumulative_final_stake > majority_threshold) + 1
    return nc



# note that this reporter cannot be used with multiprocessing (i.e. with the way batch-run currently works)
def get_min_aggregate_pledge(model):
    """
    Solve optimisation problem using solver
    """

    pools = model.get_pools_list()
    if len(pools) == 0:
        return 0

    ids = [pool.id for pool in pools]
    pledges = [pool.pledge for pool in pools]
    stakes = [pool.stake for pool in pools]
    items = len(ids)

    # Create model
    g = GEKKO()
    # Variables
    x = g.Array(g.Var, items, lb=0, ub=1, integer=True)
    # Objective
    g.Minimize(g.sum([pledges[i] * x[i] for i in range(items)]))
    # Constraint
    lower_bound = sum(stakes) / 2
    g.Equation(g.sum([stakes[i] * x[i] for i in range(items)]) >= lower_bound)
    # Optimize with APOPT
    g.options.SOLVER = 1

    try:
        g.solve(disp=False)  # choose disp = True to print details while running
    except Exception as e:  # todo catch specific errors
        print("Min aggregate pledge not found")
        return -2

    min_aggr_pledge = g.options.objfcnval
    return min_aggr_pledge


def get_pledge_rate(model):
    """
    Pledge rate is defined as: total_pledge / total_active_stake
    :param model: instance of the simulation
    :return: the pledge rate of the model at its current state
    """
    pools = model.get_pools_list()
    if len(pools) == 0:
        return 0
    total_active_stake = fsum([pool.stake for pool in pools])
    total_pledge = fsum([pool.pledge for pool in pools])
    return total_pledge / total_active_stake


def get_homogeneity_factor(model):
    """
    Shows how homogeneous the pools are
    :param model:
    :return:
    """
    pools = model.get_pools_list()
    pool_count = len(pools)
    if pool_count == 0:
        return 0
    pool_stakes = [pool.stake for pool in pools]
    max_stake = max(pool_stakes)

    ideal_area = pool_count * max_stake
    actual_area = fsum(pool_stakes)

    return actual_area / ideal_area


def get_iterations(model):
    return model.schedule.steps


def get_avg_stk_rnk(model):
    pools = model.get_pools_list()
    all_agents = model.get_agents_dict()
    stakes = {agent_id: agent.stake for agent_id, agent in all_agents.items()}
    stake_ranks = hlp.calculate_ranks(stakes)
    pool_owner_stk_ranks = [stake_ranks[pool.owner] for pool in pools]
    return round(statistics.mean(pool_owner_stk_ranks)) if len(pool_owner_stk_ranks) > 0 else 0


def get_avg_cost_rnk(model):
    pools = model.get_pools_list()
    all_agents = model.get_agents_dict()
    negative_cost_ranks = hlp.calculate_ranks({agent_id: -agent.cost for agent_id, agent in all_agents.items()})
    pool_owner_cost_ranks = [negative_cost_ranks[pool.owner] for pool in pools]
    return round(statistics.mean(pool_owner_cost_ranks)) if len(pool_owner_cost_ranks) > 0 else 0


def get_median_stk_rnk(model):
    pools = model.get_pools_list()
    all_agents = model.get_agents_dict()
    stakes = {agent_id: agent.stake for agent_id, agent in all_agents.items()}
    stake_ranks = hlp.calculate_ranks(stakes)
    pool_owner_stk_ranks = [stake_ranks[pool.owner] for pool in pools]
    return round(statistics.median(pool_owner_stk_ranks)) if len(pool_owner_stk_ranks) > 0 else 0


def get_median_cost_rnk(model):
    pools = model.get_pools_list()
    all_agents = model.get_agents_dict()
    negative_cost_ranks = hlp.calculate_ranks({agent_id: -agent.cost for agent_id, agent in all_agents.items()})
    pool_owner_cost_ranks = [negative_cost_ranks[pool.owner] for pool in pools]
    return round(statistics.median(pool_owner_cost_ranks)) if len(pool_owner_cost_ranks) > 0 else 0


def get_pool_splitter_count(model):
    pools = model.get_pools_list()
    if len(pools) == 0:
        return 0
    pool_operators = [pool.owner for pool in pools]
    cnt = collections.Counter(pool_operators)
    pool_splitters = [k for k, v in cnt.items() if v > 1]

    return len(pool_splitters)


def get_cost_efficient_count(model):
    all_agents = model.get_agents_list()
    potential_profits = [
        hlp.calculate_potential_profit(reward_scheme=model.reward_scheme, stake=agent.stake,is_private=False)
        for agent in all_agents
    ]
    positive_potential_profits = [pp for pp in potential_profits if pp > 0]
    return len(positive_potential_profits)


def get_pool_stakes_by_agent(model): # this one returns a list
    num_agents = model.n
    pool_stakes = [0 for _ in range(num_agents)]
    current_pools = model.get_pools_list()
    for pool in current_pools:
        pool_stakes[pool.owner] += pool.stake
    return pool_stakes


def get_pool_stakes_by_agent_id(model): # this one returns a dict
    num_agents = model.n
    pool_stakes = {i: 0 for i in range(num_agents)}
    current_pools = model.get_pools_list()
    for pool in current_pools:
        pool_stakes[pool.owner] += pool.stake
    return pool_stakes


def gini_coefficient(np_array):
    """Compute Gini coefficient of array of values
    using the fact that their Gini coefficient is half their relative mean absolute difference,
    as noted here: https://en.wikipedia.org/wiki/Mean_absolute_difference#Relative_mean_absolute_difference """
    diffsum = 0  # sum of absolute differences
    for i, xi in enumerate(np_array[:-1], 1):
        diffsum += np.sum(np.abs(xi - np_array[i:]))
    return diffsum / (len(np_array) * sum(np_array)) if sum(np_array) != 0 else -1


def get_gini_id_coeff_pool_count(model):
    # gather data
    pools = model.get_pools_list()
    # todo check later if you can abstract this to a function that serves this one, NC and others
    pools_owned = collections.defaultdict(lambda: 0)
    for pool in pools:
        pools_owned[pool.owner] += 1
    pools_per_agent = np.fromiter(pools_owned.values(), dtype=int)
    return gini_coefficient(pools_per_agent)

'''
def get_gini_id_coeff_pool_count_k_agents(model):
    # use at least k agents (if there aren't k pool operators, pad with non-pool operators)
    pools = model.get_pools_list()
    pools_owned = collections.defaultdict(lambda: 0)
    for pool in pools:
        pools_owned[pool.owner] += 1
    pools_per_agent = np.fromiter(pools_owned.values(), dtype=int)
    if pools_per_agent.size < model.reward_scheme.k:
        missing_values = model.reward_scheme.k - pools_per_agent.size
        pools_per_agent = np.append(pools_per_agent, np.zeros(missing_values, dtype=int))
    return gini_coefficient(pools_per_agent)
'''

def get_gini_id_coeff_stake(model):
    pools = model.get_pools_list()
    stake_controlled = collections.defaultdict(lambda: 0)
    for pool in pools:
        stake_controlled[pool.owner] += pool.stake
    stake_per_agent = np.fromiter(stake_controlled.values(), dtype=float)
    return gini_coefficient(stake_per_agent)


def get_gini_id_coeff_stake_k_agents(model):
    pools = model.get_pools_list()
    stake_controlled = collections.defaultdict(lambda: 0)
    for pool in pools:
        stake_controlled[pool.owner] += pool.stake
    stake_per_agent = np.fromiter(stake_controlled.values(), dtype=float)
    if stake_per_agent.size < model.reward_scheme.k:
        missing_values = model.reward_scheme.k - stake_per_agent.size
        stake_per_agent = np.append(stake_per_agent, np.zeros(missing_values, dtype=int))
    return gini_coefficient(stake_per_agent)


def get_total_delegated_stake(model):
    pools = model.get_pools_list()
    del_stake = fsum([pool.stake-pool.pledge for pool in pools])
    return del_stake


def get_active_stake_agents(model):
    return fsum([agent.stake for agent in model.schedule.agents])


def get_stake_distr_stats(model):
    stake_distribution = np.array([agent.stake for agent in model.schedule.agents])
    return stake_distribution.max(), stake_distribution.min(), stake_distribution.mean(), np.median(
        stake_distribution), stake_distribution.std()


def get_operator_count(model):
    counted_owners = set()  # Create a set to track counted owners
    unique_owners = 0  # Initialize the count of unique owners

    for pool in model.get_pools_list():
        if pool.owner not in counted_owners:
            counted_owners.add(pool.owner)  # Add the owner to the set
            unique_owners += 1  # Increment the count

    return unique_owners  # Return the count of unique owners


def get_total_pool_stake(model):
    current_pools = model.get_pools_list()
    if len(current_pools) == 0:
        return 0
    stakes = [pool.stake for pool in current_pools]
    return fsum(stakes)

def calculate_HHI(model):
    agents = model.schedule.agents
    pool_share=[]
    pools=model.pools
    #print("pools",pools)
    for agent in agents:
        agent_owned_pools=agent.get_owned_pools()
        #print("agent_owned_pools",agent_owned_pools)
        agent_owned_pools_stake = [pool.stake for pool in agent_owned_pools]
        agent_market_share = fsum(agent_owned_pools_stake)
        pool_share.append(agent_market_share)
    hhi=hlp.calculate_hhi(pool_share)
    return hhi

def get_total_cost(model):
    pools=model.get_pools_list()
    total_cost=0
    for pool in pools:
        total_cost+=pool.cost

    return total_cost

def get_total_delegate(model):
    pools=model.get_pools_list()
    total_delegate=0
    for pool in pools:
        for delegator in pool.delegators.values():
            total_delegate+=delegator

    return total_delegate

def get_unused_stake(model):
    total_stake = fsum([agent.stake for agent in model.schedule.agents])
    total_pledge=get_total_pledge(model)
    total_delegate=get_total_delegate(model)
    return total_stake-total_pledge-total_delegate

def get_insurance_stake(model):
    pools=model.get_pools_list()
    total_insurance=0
    for pool in pools:
        total_insurance+=pool.insurance
    return total_insurance

def get_liquidity_gain_percent(model):
    total_delegate=get_total_delegate(model)
    total_stake=fsum([pool.stake for pool in model.get_pools_list()])
    total_delegate*model.liquidity
    if total_stake==0:
        return 0
    return total_delegate/total_stake*model.liquidity





ALL_MODEL_REPORTEERS = {
    #stakes
    "Total pledge": get_total_pledge,
    "Mean pledge": get_avg_pledge,
    "Median pledge": get_median_pledge,
    "Pledge rate": get_pledge_rate,
    "Total delegated stake": get_total_delegated_stake,
    "Total pool stake": get_total_pool_stake,
     "Total insurance": get_insurance_stake,
    
    #operators
    "Operator count": get_operator_count,
    "Average pools per operator": get_avg_pools_per_operator,
    "Max pools per operator": get_max_pools_per_operator,
    "Median pools per operator": get_median_pools_per_operator,
    "Cost efficient stakeholders": get_cost_efficient_count,
    

    #decentralization
    "Nakamoto coefficient": get_nakamoto_coefficient,
    "Statistical distance": get_controlled_stake_distr_stat_dist,
    "Min-aggregate pledge": get_min_aggregate_pledge,
    "Pool homogeneity factor": get_homogeneity_factor,
    "HHI": calculate_HHI,
    "Gini-agent coefficient": get_gini_id_coeff_pool_count,
    "Gini-agent stake coefficient": get_gini_id_coeff_stake,
    
    #other
    "Pool count": get_number_of_pools,
    "Mean margin": get_avg_margin,
    "Median margin": get_median_margin,
    "Liquidity Gain percent": get_liquidity_gain_percent,
    "Total cost":get_total_cost,
    "Iterations": get_iterations,
}

REPORTER_IDS = {
    1: "Total pledge",
    2: "Mean pledge",
    3: "Median pledge",
    4: "Pledge rate",
    5: "Total delegated stake",
    6: "Total pool stake",
    7: "Total insurance",
    8: "Operator count",
    9: "Average pools per operator",
    10: "Max pools per operator",
    11: "Median pools per operator",
    12: "Cost efficient stakeholders",
    13: "Nakamoto coefficient",
    14: "Statistical distance",
    15: "Min-aggregate pledge",
    16: "Pool homogeneity factor",
    17: "HHI",
    18: "Gini-agent coefficient",
    19: "Gini-agent stake coefficient",
    20: "Pool count",
    21: "Mean margin",
    22: "Median margin",
    23: "Liquidity Gain percent",
    24: "Total cost",
    25: "Iterations"
}
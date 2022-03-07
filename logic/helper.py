# -*- coding: utf-8 -*-
"""
Created on Sun Jun 13 08:15:26 2021

@author: chris
"""
from numpy.random import default_rng
from scipy import stats
import csv
import pandas as pd
import pathlib
from math import sqrt

TOTAL_EPOCH_REWARDS_R = 1
MAX_NUM_POOLS = 1000
MIN_STAKE_UNIT = 2.2e-17
MIN_COST_PER_POOL = 1e-6


def generate_stake_distr_pareto(num_agents, total_stake=1, pareto_param=2, seed=156, truncation_factor=-1):
    """
    Generate a distribution for the players' initial stake (wealth),
    sampling from a Pareto distribution
    :param pareto_param:
    :param num_agents:
    :param total_stake:
    :return:
    """
    rng = default_rng(seed=seed)
    # Sample from a Pareto distribution with the specified shape
    stake_sample = list(rng.pareto(pareto_param, num_agents))
    if truncation_factor > 0:
        # rejection sampling to ensure that the distribution is truncated
        while True:
            max_value = max(stake_sample)
            if max_value > sum(stake_sample) / truncation_factor:
                stake_sample.remove(max_value)
                stake_sample.append(rng.pareto(pareto_param))
            else:
                break
    if total_stake > 0:
        stake_sample = normalize_distr(stake_sample, normal_sum=total_stake)
    print(max(stake_sample))
    return stake_sample


def generate_stake_distr_file(filename, num_agents, total_stake=1, seed=156):
    # Sample from file that contains the (real) stake distribution
    #distribution_file = 'stake_distribution_275.csv'
    rng = default_rng(seed=seed)
    stakes = []
    with open(filename) as file:
        reader = csv.reader(file)
        # todo replace with sth more efficient (e.g. pandas)
        for i, row in enumerate(reader):
            if i > 0:  # skip header row
                stake = float(row[-1])  # the last column represents the wallet's stake
                if stake > 0:
                    stakes.append(stake)
    stake_sample = rng.choice(stakes, num_agents, replace=False)
    normalized_stake_sample = normalize_distr(stake_sample, normal_sum=total_stake)
    return normalized_stake_sample


def generate_stake_distr_flat(num_agents, total_stake=1):
    stake_per_agent = total_stake / num_agents if num_agents > 0 else 0
    return [stake_per_agent for _ in range(num_agents)]


def generate_cost_distr_unfrm(num_agents, low, high, seed=156):
    """
    Generate a distribution for the players' costs of operating pools,
    sampling from a uniform distribution
    :param num_agents:
    :param low:
    :param high:
    :return:
    """
    rng = default_rng(seed=seed)
    costs = rng.uniform(low=low, high=high, size=num_agents)
    return costs


def generate_cost_distr_bands(num_agents, low, high, num_bands, seed=156):
    rng = default_rng(seed=seed)
    bands = rng.uniform(low=low, high=high, size=num_bands)
    costs = rng.choice(bands, num_agents)
    return costs


def generate_cost_distr_nrm(num_agents, low, high, mean, stddev):
    """
    Generate a distribution for the players' costs of operating pools,
    sampling from a truncated normal distribution
    """
    costs = stats.truncnorm.rvs(low, high,
                                loc=mean, scale=stddev,
                                size=num_agents)
    return costs


def normalize_distr(dstr, normal_sum=1):
    """
    returns an equivalent distribution where the sum equals 1 (or another value defined by normal_sum)
    :param dstr:
    :param normal_sum:
    :return:
    """
    s = sum(dstr)
    if s == 0:
        return dstr
    nrm_dstr = [normal_sum * i / s for i in dstr]
    flt_error = normal_sum - sum(nrm_dstr)
    nrm_dstr[-1] += flt_error
    return nrm_dstr


def calculate_potential_profit(pledge, cost, alpha, beta, reward_function_option):
    """
    Calculate a pool's potential profit, which can be defined as the profit it would get at saturation level

    :param pledge:
    :param cost:
    :param alpha:
    :param beta:
    :return: float, the maximum possible profit that this pool can yield
    """
    potential_reward = calculate_pool_reward(beta, pledge, alpha, beta, reward_function_option)
    return potential_reward - cost


def calculate_current_profit(stake, pledge, cost, alpha, beta, reward_function_option):
    reward = calculate_pool_reward(stake, pledge, alpha, beta, reward_function_option)
    return reward - cost

def calculate_pool_reward(stake, pledge, alpha, beta, reward_function_option, curve_root=3, crossover_factor=8):
    if reward_function_option == 0:
        return calculate_pool_reward_old(stake, pledge, alpha, beta)
    elif reward_function_option == 1:
        return calculate_pool_reward_new(stake, pledge, alpha, beta)
    elif reward_function_option == 2:
        return calculate_pool_reward_alternative_1(stake, pledge, alpha, beta)
    elif reward_function_option == 3:
        return calculate_pool_reward_alternative_2(stake, pledge, alpha, beta)
    elif reward_function_option == 4:
        return calculate_pool_reward_curve_pledge_benefit(stake, pledge, alpha, beta, curve_root, crossover_factor)
    elif reward_function_option == 5:
        return calculate_pool_reward_curve_pledge_benefit_min_first(stake, pledge, alpha, beta, curve_root, crossover_factor)
    elif reward_function_option == 6:
        return calculate_pool_reward_curve_pledge_benefit_no_min(stake, pledge, alpha, beta, curve_root, crossover_factor)
    else:
        raise ValueError("Invalid option for reward function.")


def calculate_pool_reward_old(stake, pledge, alpha, beta):
    pledge_ = min(pledge, beta)
    stake_ = min(stake, beta)
    r = (TOTAL_EPOCH_REWARDS_R / (1 + alpha)) * (stake_ + (pledge_ * alpha * ((stake_ - pledge_ * (1 - stake_ / beta)) / beta)))
    return r


def calculate_pool_reward_new(stake, pledge, alpha, beta):
    pledge_ = min(pledge, beta)
    stake_ = min(stake, beta)
    r = (TOTAL_EPOCH_REWARDS_R / (1 + alpha)) * stake_ * (1 + (alpha * pledge_ / beta))
    return r


def calculate_pool_reward_alternative_1(stake, pledge, alpha, beta):
    """
    community-proposed reward sharing function
    """
    pledge_ = min(pledge, beta)
    stake_ = min(stake, beta)
    r = (TOTAL_EPOCH_REWARDS_R / (1 + alpha)) * (stake_ + alpha * pledge_)
    return r


def calculate_pool_reward_alternative_2(stake, pledge, alpha, beta):
    pledge_ = min(pledge, beta)
    stake_ = min(stake, beta)
    r = (TOTAL_EPOCH_REWARDS_R / (1 + alpha)) * stake_ * (1 + (alpha * sqrt(pledge_) / beta))
    return r


def calculate_pool_reward_curve_pledge_benefit(stake, pledge, alpha, beta, curve_root, crossover_factor):
    crossover = beta / crossover_factor
    pledge_ = (pledge ** (1 / curve_root)) * (crossover ** ((curve_root - 1) / curve_root))
    return calculate_pool_reward_old(stake, pledge_, alpha, beta)

def calculate_pool_reward_curve_pledge_benefit_min_first(stake, pledge, alpha, beta, curve_root, crossover_factor):
    crossover = beta / crossover_factor
    pledge = min(pledge, beta)
    pledge_ = (pledge ** (1 / curve_root)) * (crossover ** ((curve_root - 1) / curve_root))
    stake_ = min(stake, beta)
    r = (TOTAL_EPOCH_REWARDS_R / (1 + alpha)) * (
                stake_ + (pledge_ * alpha * ((stake_ - pledge_ * (1 - stake_ / beta)) / beta)))
    return r

def calculate_pool_reward_curve_pledge_benefit_no_min(stake, pledge, alpha, beta, curve_root, crossover_factor):
    crossover = beta / crossover_factor
    pledge_ = (pledge ** (1 / curve_root)) * (crossover ** ((curve_root - 1) / curve_root))
    stake_ = min(stake, beta)
    r = (TOTAL_EPOCH_REWARDS_R / (1 + alpha)) * (
                stake_ + (pledge_ * alpha * ((stake_ - pledge_ * (1 - stake_ / beta)) / beta)))
    return r


def calculate_delegator_reward_from_pool(pool, pool_reward, delegator_stake_fraction):
    margin_factor = (1 - pool.margin) * delegator_stake_fraction
    pool_profit = pool_reward - pool.cost
    r_d = margin_factor * pool_profit if pool_profit > 0 else 0
    return r_d


def calculate_operator_reward_from_pool(pool, pool_reward, operator_stake_fraction):
    margin_factor = pool.margin + ((1 - pool.margin) * operator_stake_fraction)
    pool_profit = pool_reward - pool.cost
    return pool_profit if pool_profit <= 0 else pool_profit * margin_factor


def calculate_pool_stake_NM(pool_id, pools, beta, k):
    """
    Calculate the non-myopic stake of a pool, given the pool and the state of the system (current pools)
    :param pool_id: the id of the pool that is examined
    :param pools: dictionary of pools with the pool id as key and the pool object as value
    :param beta: the saturation point of the system
    :param k: the desired number of pools of the system
    :return: the value of the non-myopic stake of the pool with id pool_id
    """
    desirabilities = {
        pool_id: pool.calculate_desirability()
        for pool_id, pool in pools.items()
    }
    potential_profits = {
        pool_id: pool.potential_profit
        for pool_id, pool in pools.items()
    }
    stakes = {
        pool_id: pool.stake
        for pool_id, pool in pools.items()
    }
    # todo this exact same calculation is performed for all potential pools. maybe cache results somehow?
    ranks = calculate_ranks(desirabilities, potential_profits, stakes, rank_ids=True)
    rank = ranks[pool_id]
    pool = pools[pool_id]
    return pool.calculate_stake_NM(k, beta, rank)


def calculate_ranks(ranking_dict, *tie_breaking_dicts, rank_ids=True):
    """
    Rank the values of a dictionary from highest to lowest (highest value gets rank 1, second highest rank 2 and so on)
    @param ranking_dict:
    @param tie_breaking_dicts:
    @param rank_ids: if True, then the lowest id (e.g. the one corresponding to a pool created earlier) takes precedence
                    during ties that persist even after the other tie breaking rules have been applied.
                    If False and ties still exist, then the tie breaking is arbitrary.
    @return: dictionary with the item id as the key and the calculated rank as the value
    """
    if rank_ids:
        tie_breaking_dicts = list(tie_breaking_dicts)
        tie_breaking_dicts.append({key: -key for key in ranking_dict.keys()})
    final_ranking_dict = {
        key:
            (ranking_dict[key],) + tuple(tie_breaker_dict[key] for tie_breaker_dict in tie_breaking_dicts)
        for key in ranking_dict
    }
    ranks = {
        sorted_item[0]: i + 1 for i, sorted_item in
        enumerate(sorted(final_ranking_dict.items(), key=lambda item: item[1], reverse=True))
    }
    return ranks


def to_latex(row_list, sim_id, output_dir):
    row_list_latex = [row[2:4] + row[5:8] + row[9:10] + row[12:14] for row in row_list]
    df = pd.DataFrame(row_list_latex[1:], columns=row_list_latex[0])
    # shift desirability rank column to first position to act as index
    first_column = df.pop('Pool desirability rank')
    df.insert(0, 'Pool desirability rank', first_column)
    sorted_df = df.sort_values(by=['Pool desirability rank'], ascending=True)

    path = pathlib.Path.cwd() / output_dir
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)
    with open(output_dir + sim_id + "-output.tex", 'w', newline='') as file:
        sorted_df.to_latex(file, index=False)


def generate_execution_id(args_dict):
    num_args_to_use = 4
    max_characters = 100
    return "".join([str(key) + '-' + str(value) + '-' for key, value in list(args_dict.items())[:num_args_to_use]
                    if type(value) == bool or type(value) == int or type(value) == float])[:max_characters]


def calculate_cost_per_pool(num_pools, initial_cost, cost_factor):
    """
    Calculate the average cost of an agent's pools, assuming that any additional pool costs less than the previous one
    Specifically if the first pool costs c1 and we use a factor of 0.6 then a second pool would cost c2 = 0.6 * c1,
    a third pool would cost c3 = 0.6 * c2 = 0.6^2 * c1, and so on. Can be calculated using the sum of a geometrical sequence.
    @param num_pools:
    @param initial_cost:
    @param cost_factor:
    @return:
    """
    if cost_factor < 1:
        return max((initial_cost * (1 - cost_factor ** num_pools) / (1 - cost_factor)) / num_pools, MIN_COST_PER_POOL)
    else:
        return initial_cost


def calculate_cost_per_pool_fixed_fraction(num_pools, initial_cost, cost_factor):
    return (initial_cost + (num_pools - 1) * cost_factor * initial_cost) / num_pools

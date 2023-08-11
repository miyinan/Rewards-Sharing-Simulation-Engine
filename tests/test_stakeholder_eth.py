import pytest
from copy import copy

from logic.sim import Ethereum_Sim
from logic.stakeholder_eth import EthStakeholder
from logic.strategy import Strategy
import logic.helper as hlp
from logic.pool import Pool


def test_calculate_operator_utility_from_strategy():
    model=Ethereum_Sim(beta=0.2,alpha=0.1)
    model.total_stake=1
    agent = EthStakeholder(unique_id=1, model=model, stake=0.1, cost=0.001)
    pool = Pool(cost=0.05, pledge=0.1, owner=1, margin=0.1, reward_scheme=model.reward_scheme, pool_id=555)
    strategy = Strategy(owned_pools={555: pool})
    utility = agent.calculate_operator_utility_from_strategy(strategy)
    
    assert model.total_stake == 1
    assert utility == pytest.approx(0.05, abs=1e-6)


def test_close_pool():
    model=Ethereum_Sim(beta=0.2,alpha=0.1)
    pools=model.pools
    agent = EthStakeholder(unique_id=156, model=model, stake=0.1, cost=0.001)
    pool = Pool(cost=0.001, pledge=0.1, owner=156, margin=0.2, reward_scheme=model.reward_scheme, pool_id=555)
    model.pools[555] = pool
    model.pool_rankings.add(pool)
    
    agent.close_pool(555)

    assert 555  not in model.pools.keys()
'''
    # try to close the same pool again but get an exception because it doesn't exist anymore
    with pytest.raises(ValueError) as e_info:
        agent.close_pool(555)
    assert str(e_info.value) == 'Given pool id is not valid.'

    # try to close another agent's pool
    with pytest.raises(ValueError) as e_info:
        model.pools[555] = pool
        agent = EthStakeholder(157, model, 0.003)
        agent.close_pool(555)
    assert str(e_info.value) == "agent tried to close pool that belongs to another agent."
'''

def test_calculate_cost_by_pool_num():
    model=Ethereum_Sim(beta=0.2,alpha=0.1,extra_pool_cost_fraction=0.4)
    agent = EthStakeholder(unique_id=1, model=model, stake=0.1, cost=0.001)
    cost = agent.calculate_cost_by_pool_num(1)
    cost2=agent.calculate_cost_by_pool_num(2)

    assert cost == pytest.approx(0.001, abs=1e-6)
    assert cost2 == pytest.approx(0.001+0.001*0.4, abs=1e-6)


def test_calculate_operator_utility_from_strategy():
    model=Ethereum_Sim(beta=0.2,alpha=0.1)
    model.total_stake=1
    agent = EthStakeholder(unique_id=1, model=model, stake=0.1, cost=0.001)
    pool = Pool(cost=0.001, pledge=0.1, owner=1, margin=0.1, reward_scheme=model.reward_scheme, pool_id=555)
    pool.stake=0.15
    pool2 = Pool(cost=0.001, pledge=0.15,owner=1, margin=0.1, reward_scheme=model.reward_scheme, pool_id=556)
    pool2.stake=0.2
    strategy1 = Strategy(owned_pools={555: pool})
    utility1 = agent.calculate_operator_utility_from_strategy(strategy1)
    
    strategy2 = Strategy(owned_pools={556: pool2})
    utility2 = agent.calculate_operator_utility_from_strategy(strategy2)

    pool2_utility = hlp.calculate_operator_utility_from_pool(
            pool_stake=pool2.stake,
            pledge=pool2.pledge,
            margin=pool2.margin,
            cost=pool2.cost,
            reward_scheme=model.reward_scheme
        )
    
    strategy3=Strategy(owned_pools={555: pool, 556: pool2})
    utility3 = agent.calculate_operator_utility_from_strategy(strategy3)
    

    assert model.total_stake == 1
    assert model.reward_scheme.alpha == 0.1
    assert model.reward_scheme.beta == 0.2
    assert model.reward_scheme.total_stake == 1
    
    assert utility2 == pytest.approx(0.154, abs=1e-6)
    assert pool2_utility == pytest.approx(0.154, abs=1e-6)
    assert utility1 == pytest.approx(0.104, abs=1e-6)
    assert utility3 == pytest.approx(0.258, abs=1e-6)   



def test_find_delegation_move():
    model=Ethereum_Sim(beta=0.2,alpha=0.1)
    agent156 = EthStakeholder(156, model, stake=0.001, cost=0.001)
    agent157 = EthStakeholder(157, model, stake=0.005, cost=0.001)
    agent158 = EthStakeholder(158, model, stake=0.003, cost=0.001)
    agent159 = EthStakeholder(159, model, stake=0.0001, cost=0.001)
    pool555 = Pool(cost=0.001, pledge=0.05, owner=156, reward_scheme=model.reward_scheme, pool_id=555, margin=0.1)
    model.pools[555] = pool555
    pool556 = Pool(cost=0.001, pledge=0.05, owner=157, reward_scheme=model.reward_scheme, pool_id=556, margin=0.15)
    model.pools[556] = pool556
    pool557 = Pool(cost=0.001, pledge=0.05, owner=157, reward_scheme=model.reward_scheme, pool_id=557, margin=0.2)
    model.pools[557] = pool557
    pool558 = Pool(cost=0.001, pledge=0.05, owner=158, reward_scheme=model.reward_scheme, pool_id=558, margin=0.0)
    model.pools[558] = pool558
    
    model.pool_rankings.add(pool555)
    model.pool_rankings.add(pool556)
    model.pool_rankings.add(pool557)
    model.pool_rankings.add(pool558)

    
    
    

    # one pool with higher desirability, choose that,skip the private one(margin == 0)
    delegator_strategy = agent159.find_delegation_move()
    allocations = delegator_strategy.stake_allocations
    assert allocations.keys() == {555}
    assert allocations[555] == 0.0001

    # ties in desirability and potential profit, break with stake
    pool558.margin = 0.1
    pool558.stake = 0.007
    delegator_strategy = agent159.find_delegation_move()
    allocations = delegator_strategy.stake_allocations
    assert allocations.keys() == {558}
    assert allocations[558] == 0.0001

    # although pool 558,555 has lower margin, but saturated now
    pool558.stake = 0.2
    pool555.stake = 0.2
    delegator_strategy = agent159.find_delegation_move()
    allocations = delegator_strategy.stake_allocations
    assert allocations.keys() == {556}
    assert allocations[556] == 0.0001

    # all pools saturated, choose the one with highest desirability
    pool558.stake = 0.2
    pool557.stake = 0.2
    pool555.stake = 0.2
    pool556.stake = 0.2
    delegator_strategy = agent158.find_delegation_move()
    allocations = delegator_strategy.stake_allocations
    assert allocations == {}
    assert pool558.margin == 0.1


def test_execute_strategy(mocker):
    model=Ethereum_Sim(beta=0.2,alpha=0.1)
    agent1 = EthStakeholder(unique_id=1, model=model, stake=0.1, cost=0.001)
    agent2= EthStakeholder(unique_id=2, model=model, stake=0.05, cost=0.001)
    agent3 = EthStakeholder(unique_id=3, model=model, stake=0.001, cost=0.001)
    agent4 = EthStakeholder(unique_id=4, model=model, stake=0.05, cost=0.001)
    
    agents_dict = {1:agent1, 2:agent2, 3:agent3, 4:agent4}
    mocker.patch('logic.sim.Simulation.get_agents_dict',return_value=agents_dict)

    #setting: there are two pools, one of them has two delegators and the other has one
    pool1=Pool(cost=0.001, pledge=0.1, owner=1, margin=0.1, reward_scheme=model.reward_scheme, pool_id=1)
    pool2=Pool(cost=0.001, pledge=0.05, owner=2, margin=0.1, reward_scheme=model.reward_scheme, pool_id=2)
    model.pools[1]=pool1
    model.pools[2]=pool2
    model.pool_rankings.add(pool1)
    model.pool_rankings.add(pool2)

    agent1.strategy=Strategy(stake_allocations=None, owned_pools={1:pool1})
    agent2.strategy=Strategy(stake_allocations=None, owned_pools={2:pool2})
    agent3.strategy=Strategy(stake_allocations={1:0.001}, owned_pools=None)
    agent4.strategy=Strategy(stake_allocations={1:0.05}, owned_pools=None)

    pool1.stake=0.151
    pool1.delegators={3:0.001, 4:0.05}

    #new strategy for pool owner, change cost
    pool1_copy=copy(pool1)
    pool1_copy.cost=0.0008
    new_strategy1=Strategy(stake_allocations=None, owned_pools={1:pool1_copy})
    agent1.new_strategy=new_strategy1
    agent1.execute_strategy()

    assert agent1.strategy==new_strategy1
    assert agent1.new_strategy is None
    assert model.pools[1].cost == 0.0008
    assert model.pools[1].stake == 0.151

    


    
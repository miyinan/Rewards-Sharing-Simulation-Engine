import random

import pytest
import logic.helper as hlp
from logic.reward_schemes import Ethereum
from logic.sim import Ethereum_Sim

from logic.pool import Pool


def test_calculate_pool_reward():
    model=Ethereum_Sim()
    model.total_stake=1
    reward_scheme = Ethereum(model=model,alpha=0.1, beta=0.2)
    r=reward_scheme.calculate_pool_reward(0.2)
    
    assert r==0.2
    assert reward_scheme.total_stake==1
    assert reward_scheme.alpha==0.1
    assert reward_scheme.beta==0.2

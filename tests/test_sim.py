import pytest

from logic.stakeholder import Stakeholder
from logic.sim import Ethereum_Sim


def test_Ethereum_Sim():
    model = Ethereum_Sim(alpha=0.1, beta=0.2)
    
    assert model.alpha == 0.1

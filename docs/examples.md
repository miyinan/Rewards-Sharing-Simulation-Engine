# Examples

Here, we provide some examples that can help better understand the capacities of the simulation engine. Note that in all examples below, we assume that the ``python`` command corresponds to a Python 3.9 installation and that the commands are executed from the root directory of the project. Recall that when an argument is not set explicitly then its default value is used.



## Single runs

Run with 1000 agents, alpha = 1 and beta=2:

    python main.py --n=1000 --alpha=1 --beta=2 --execution_id=baseline

Run with two phases, first with n = 100 and then n = 200, others configurations keep default:

    python main.py --n 100 200 --execution_id=increasing-n

Run with 3,000 agents, alpha = 1 and a specified seed (42):

    python main.py --n=3000 --alpha=1 --seed=42 --execution_id=n-3000-alpha-1-seed-42

Run with agents in hard mood where they can choose margin:

    python main.py --agent_profile=hard

Run with agents in hard mood where they don't have liquidity reward by holding LSD(liquid staking tokens):

    python main.py --liquidity=0







## Batch runs

In batch runs, when multiple values are provided for an argument then multiple simulation instances are created, one for each combination of the variable arguments.

Batch run with 1000 agents and 5 different values for beta (1.0 1.5 2.0):

    python batch-run.py --n=1000 --beta 1.0 1.5 2.0 --execution_id=batch-run-varying-beta

Batch run with 1000 agents, alpha = 2.0 and 3 different values for beta (1.0, 1.1, 1.2):

    python batch-run.py --n=1000 --beta=2.0 --alpha 1 1.1 1.2 --execution_id=batch-run-varying-a0

Batch run with two variables, using 3 values for beta and 3 values for alpha (total of 9 combinations):

    python batch-run.py --n=500 --k  1.5 2 --alpha 1.0 1.5 --execution_id=batch-run-varying-k-a0-3x3


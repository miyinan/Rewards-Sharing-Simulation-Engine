# Rewards Sharing Simulation Engine for Ethereum- Documentation

This is the documentation for the Rewards Sharing Simulation Engine for Ethereum. 

This project is forked from the University of Edinburgh's Blockchain Technology Lab, Reward Sharing Simulation Engine  and extend to Ethereum. To know more about the original project, the source code is available on [Github](https://github.com/Blockchain-Technology-Lab/Rewards-Sharing-Simulation-Engine).

## Overview

The simulation use Agent-Based-Modeling to models the behaviour of stakeholders in a Proof-of-Stake system, i.e. the way they use their stake to engage with the protocol depending on the rewards they expect to receive. It focuses particularly on the way different stakeholders combine their resources and create stake pools (it assumes an on-chain pooling mechanism like the one in Cardano) and follows the dynamics of the system until it (potentially) reaches an equilibrium. The implementation is based on the Ethereum blockchain.

The simulation engine can be used to play out different scenarios and better understand the relationship between the
system's input (e.g. parameters of the reward scheme or initial stake distribution) and its convergence properties (does
it converge to an equilibrium and if yes how quickly, how decentralized is the final allocation of stake to the
different stakeholders, and so on).

For details on how to install the engine and run simulations, see the [Setup](setup.md) page; for a complete guide on
how to customize the simulation, see the [Configuration](configuration.md) page; for a description of the different
output files that a simulation produces, see the [Output](output.md) page, and for examples to get started with and
draw inspiration from, see the [Examples](examples.md) page.

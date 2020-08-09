import argparse
import dill
import numpy as np
from collections import OrderedDict 

import torch
import pandas as pd

from larocs_sim.envs.drone_env import DroneEnv
from networks.structures import *
import pyrep.backend.sim  as sim






def rollouts(env, policy, action_range, max_timesteps = 1000,env_reset_mode = 'False',  time_horizon=250):

    count = 0
    dones = False
    set_of_obs,set_of_next_obs,set_of_rewards,set_of_actions,set_of_dones,set_of_infos = [],[],[],[],[],[]

    rollout=-1

    while True:
        mb_obs, mb_next_obs, mb_rewards, mb_actions, mb_dones, mb_infos = [], [], [], [], [], []
        sim.simRemoveBanner(sim.sim_handle_all)
        rollout+=1

        obs0 = env.reset()

        sim.simAddBanner(label = "Rollout = {0}".format(rollout).encode('ascii'),\
             size = 0.2,\
             options =  1,
             positionAndEulerAngles=[0,0,2.5,1.3,0,0],
             parentObjectHandle = -1)
    

        for j in range(time_horizon):
            dones = False
            if count == max_timesteps:
                set_tau = {'obs' : set_of_obs,
                'next_obs' : set_of_next_obs,
                'rewards' : set_of_rewards,
                'actions' : set_of_actions,
                'dones' : set_of_dones,
                'infos' : set_of_infos}
                return set_tau
            try:
                actions, agent_info = policy.deterministic_action(obs0)
            except:
                actions= policy.deterministic_action(obs0)


            # Take actions in env and look the results
            obs1, rewards, dones, infos = env.step(actions*action_range[1])
            ## Append on the experience buffers
            mb_obs.append(obs0.copy())
            # mb_obs.append(obs0)
            mb_next_obs.append(obs1)
            mb_actions.append(actions)
            mb_dones.append(dones)
            mb_rewards.append(rewards)
            mb_infos.append(infos)
            
            count += 1

            if dones == True:
                break

            obs0 = obs1

        print()
        print('rewards: mean = {0}'.format(np.mean(mb_rewards)))
        print('rewards: sum = {0}'.format(np.sum(mb_rewards)))

        set_of_obs.append(mb_obs)
        set_of_next_obs.append(mb_next_obs)
        set_of_rewards.append(mb_rewards)
        set_of_actions.append(mb_actions)
        set_of_dones.append(mb_dones)
        set_of_infos.append(mb_infos)


def run_policy(args):
      
    # Set environment
    env = DroneEnv(random=args.env_reset_mode, headless=args.headless, seed=args.seed, 
        reward_function_name=args.reward_function,state=args.state)

    restore_path = args.file    
    print('Loading')
    # Load parameters if necessary
    try:
        checkpoint = torch.load(restore_path, map_location='cpu')
    except:
        checkpoint = torch.load(restore_path, map_location=torch.device('cpu'))
    print('Finished Loading')

    # Neural network parameters
    action_dim = env.action_space.shape[0]
    try:
        state_dim = env.observation_space.shape[0]
    except:
        state_dim = env.observation_space
    # hidden_dim = 256
    hidden_dim = checkpoint['linear1.weight'].data.shape[0]
    action_range = [env.agent.action_space.low.min(), env.agent.action_space.high.max()]
    size_obs = checkpoint['linear1.weight'].data.shape[1]

    assert size_obs == state_dim, 'Checkpoint state must be the same as the env'

    
   # Networks instantiation
    policy_net = PolicyNetwork(state_dim, action_dim, hidden_dim).to(device)


    # Loading  Models
    policy_net.load_state_dict(checkpoint)
    print('Finished Loading the weights')

    print("Running the policy...")
    set_tau = rollouts(env, policy_net,\
            action_range, max_timesteps = args.max_timesteps,env_reset_mode = 'False',  time_horizon=args.H)
    

    print('Closing env')
    try:
        env.shutdown()
    except:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str,
                        help='path to the snapshot file')
    parser.add_argument('--H', type=int, default=250,
                        help='Max length of rollout')
    parser.add_argument('--max_timesteps', type=int, default=1000,
                        help='Max number of timesteps')
    parser.add_argument('--gpu', action='store_true',default=False)
    parser.add_argument(
        '--headless', help='To render or not the environment', choices=('True', 'False'), default='True')
    parser.add_argument(
        '--env_reset_mode', help='How to sample the starting position of the agent', choices=('Uniform', 'Gaussian','False','Discretized_Uniform'), default='False')
    parser.add_argument(
        '--seed', help='Global seed', default=42,type=int)
    parser.add_argument(
        '--reward_function', help='What reward function to use', default='Normal',type=str)
    parser.add_argument(
        '--state', help='State to be used', default='Old',type=str)
    
    
    args = parser.parse_args()


    if (args.headless) == 'False':
        args.headless = False
    else:
        args.headless = True
    if (args.env_reset_mode) == 'False':
        args.env_reset_mode = False

    run_policy(args)
    print("Done")    



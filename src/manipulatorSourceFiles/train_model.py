import torch
import time
import numpy as np
import math
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from torch.utils.data import TensorDataset, DataLoader
from torch import nn

from models import DeepONetProjected, FNOProjected, FNOGRUNet, DeepONetGRUNet
from trainer import model_trainer, evaluate_train_performance
from config import SimulationConfig, ModelConfig
from robot import Manipulator

### LOAD CONFIG ### 
# Config can be loaded through config.dat or specified for this file in particular using the settings
# below. 
sim_config_path = "../../config/manipulatorConfig/config.toml"
sim_config = SimulationConfig(sim_config_path)

model_config_path = "../../config/manipulatorConfig/deeponet.toml"
model_config = ModelConfig(model_config_path)

print(sim_config.dataset_filename)

# Ensure that our data and model will live on the same cpu/gpu device. 
assert(model_config.device == sim_config.device)
torch.set_default_device(sim_config.device_name)

inputs = np.load("../../datasets/ManipulatorDatasets/inputs" + sim_config.dataset_filename+".npy").astype(np.float32)
outputs = np.load("../../datasets/ManipulatorDatasets/outputs" + sim_config.dataset_filename + ".npy").astype(np.float32)

x_train, x_test, y_train, y_test = train_test_split(inputs, outputs, test_size=sim_config.test_size, random_state=sim_config.random_state)
x_train = torch.from_numpy(x_train).to(sim_config.device)
x_test = torch.from_numpy(x_test).to(sim_config.device)
y_train = torch.from_numpy(y_train).to(sim_config.device)
y_test = torch.from_numpy(y_test).to(sim_config.device)

trainData = DataLoader(TensorDataset(x_train, y_train), batch_size=sim_config.batch_size, shuffle=True, generator=torch.Generator(device=sim_config.device))
testData = DataLoader(TensorDataset(x_test, y_test), batch_size=sim_config.batch_size, shuffle=False, generator=torch.Generator(device=sim_config.device))

match model_config.model_type:
    case "DeepONet":
        spatial = np.arange(0, sim_config.D, sim_config.dt/(3*sim_config.dof)).astype(np.float32)
        grid=torch.from_numpy(spatial.reshape((len(spatial), 1))).to(sim_config.device)
        model_config.update_config(input_channel=grid.shape[0], output_channel=sim_config.nD*2*sim_config.dof)
        model = DeepONetProjected(model_config.dim_x, model_config.hidden_size, model_config.num_layers, model_config.input_channel, model_config.output_channel, grid, sim_config.dof, sim_config.nD)
    case "FNO":
        model_config.update_config(input_channel=3*sim_config.dof, output_channel=2*sim_config.dof)
        model = FNOProjected(model_config.hidden_size, model_config.num_layers, model_config.modes, model_config.input_channel, model_config.output_channel, sim_config.dof, sim_config.nD)
    case "FNO+GRU":
        model_config.update_config(input_channel=3*sim_config.dof, output_channel=2*sim_config.dof)
        model = FNOGRUNet(model_config.fno_num_layers, model_config.gru_num_layers, model_config.fno_hidden_size, model_config.gru_hidden_size, model_config.modes, model_config.input_channel, model_config.output_channel, sim_config.dof, sim_config.nD)
    case "DeepONet+GRU":
        spatial = np.arange(0, sim_config.D, sim_config.dt/(3*sim_config.dof)).astype(np.float32)
        grid=torch.from_numpy(spatial.reshape((len(spatial), 1))).to(sim_config.device)
        model_config.update_config(input_channel=grid.shape[0], output_channel=sim_config.nD*2*sim_config.dof)
        model = DeepONetGRUNet(model_config.dim_x, model_config.deeponet_num_layers, model_config.gru_num_layers, model_config.deeponet_hidden_size, model_config.gru_hidden_size, model_config.input_channel, model_config.output_channel, grid, sim_config.dof, sim_config.nD)
    case _:
        raise Exception("Model type not supported. Please use GRU, FNO, DeepONet, LSTM, DeepONet+GRU, FNO+GRU.")

model.to(sim_config.device)
print("Model parameters:", sum(p.numel() for p in model.parameters() if p.requires_grad))
# Saves the best test loss model in the locations "models/model_filename"
# Saves the loss function curve to this directory
model, train_loss_arr, test_loss_arr = model_trainer(model, trainData, testData, model_config.epochs, sim_config.batch_size, model_config.gamma, model_config.learning_rate, model_config.weight_decay, model_config.model_type, model_config.model_filename)
evaluate_train_performance(model, model_config.model_type, train_loss_arr, test_loss_arr)

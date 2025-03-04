import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pymc as pm
import pytensor
import seaborn as sns
import pandas as pd
import pytensor.tensor as pt
from tqdm import tqdm

from sklearn.model_selection import train_test_split

# Create the neural network model
cosine_count = 1

# Microphone array
SourceLocation = [-0.20049999999999987,0.21884]
ReceiverLocationsX =[-0.131500000000000,-0.112000000000000,-0.0924999999999999,
-0.0719999999999999,-0.0514999999999999,-0.0309999999999999,-0.0104999999999999,0.00750000000000015,
0.0290000000000001,0.0480000000000001,0.0685000000000001,0.0900000000000001,0.109500000000000,
0.129000000000000,0.151000000000000,0.166500000000000,0.187500000000000,
0.208000000000000,0.229500000000000,0.249500000000000,0.268500000000000,
0.289000000000000,0.310000000000000,0.327500000000000,0.347500000000000,
0.368500000000000,0.389000000000000,0.409500000000000,0.426500000000000,
0.448500000000000,0.467000000000000,0.488500000000000,0.508500000000000,
0.528000000000000]
ReceiverLocationsY = [0.283024319442090,
                        0.283006369700232,
                        0.283208419958374,
                        0.283436216383600,
                        0.283364012808826,
                        0.283731809234052,
                        0.283969605659278,
                        0.283593036666793,
                        0.283656579259103,
                        0.284565756433703,
                        0.283773552858929,
                        0.283947095451239,
                        0.283819145709381,
                        0.284651195967522,
                        0.284087611643374,
                        0.284616677233179,
                        0.284777346741947,
                        0.285195143167173,
                        0.284838685759483,
                        0.285313609101167,
                        0.285382786275767,
                        0.285680582700993,
                        0.284461252209761,
                        0.284291810133734,
                        0.284866733475418,
                        0.285097402984186,
                        0.286005199409412,
                        0.285352995834638,
                        0.285200680675069,
                        0.286317096350921,
                        0.286443400441979,
                        0.286756943034289,
                        0.287121866375973,
                        0.286673916634115]
RecLoc = []
for i in range(len(ReceiverLocationsX)):
    RecLoc.append([ReceiverLocationsX[i],ReceiverLocationsY[i]])

SourceAngle = np.pi / 3

from src.AcousticParameterMCMC import AcousticParameterMCMC
from src.Directed2DVectorized import Directed2DVectorised
from src.SymbolicMath import SymCosineSurfaceM

train_count = 5_000
sample_count = 100_000 # Hard coded for now
params_raw = np.array(AcousticParameterMCMC.LoadCSVData("results/examples/nuts-3-param-real-data-110K_IT/NUTS.csv")[:sample_count]).reshape(sample_count, -1)

b = np.random.choice(range(sample_count),train_count)
params = []
for i in range(0, train_count):
    params.append(params_raw[b[i]])
params = np.array(params)

print("Loaded previous trace: ", params.shape)

factor = AcousticParameterMCMC.GenerateFactor(SourceLocation, SourceAngle, RecLoc, 0.02, 14_000, 700)
def generate_microphone_pressure(parameters,uSamples=700):
    def newFunction(x):
        return SymCosineSurfaceM(x, parameters[0], parameters[1], parameters[2])

    KA_Object = Directed2DVectorised(SourceLocation,RecLoc,newFunction,14_000,0.02,SourceAngle,'simp',userMinMax=[-1,1],userSamples=uSamples,absolute=False)
    scatter = KA_Object.Scatter(absolute=True,norm=False)
    return scatter/factor   

# Generating responses
scatters = []
for i in tqdm (range(train_count), desc="Generating param responses"):
    scatters.append(generate_microphone_pressure(params[i]))
scatters = np.array(scatters)

training_data = np.concatenate((params, scatters), axis=1)
print("Combined params and scatter responses: ", training_data.shape)

# Setup training data
# Create pandas dataframe (currently hard coded to 3 param recovery! TODO: maybe make more generic)
# Split into test and training sets
columns = ['amp', 'wl', 'phase']
for i in range(0, scatters.shape[1]):
  columns.append('r' + str(i))

dataframe = pd.DataFrame(training_data,
                   columns=columns)

# X3 contains the receiver data
# Y3 contains the parameter data
X3_train, X3_test, Y3_train, Y3_test = train_test_split(
    dataframe[columns[3*cosine_count:]], dataframe[columns[:3*cosine_count]], test_size=0.25, random_state=11)

# Initialize weights for network
n_hidden_1 = scatters.shape[1] # Should be 34 for receiver count
n_hidden_2 = n_hidden_1

np.random.seed(42)
floatX = pytensor.config.floatX

init_1 = np.random.randn(X3_train.shape[1], n_hidden_1).astype(floatX)
init_2 = np.random.randn(n_hidden_1, n_hidden_2).astype(floatX)
init_out = np.random.randn(n_hidden_2,Y3_train.shape[1]).astype(floatX)

init_out_amp = np.random.randn(n_hidden_2, 1).astype(floatX)
init_out_wl = np.random.randn(n_hidden_2, 1).astype(floatX)
init_out_phase = np.random.randn(n_hidden_2, 1).astype(floatX)

# Initialize random biases in each layer
init_b_1 = np.random.randn(n_hidden_1).astype(floatX)
init_b_2 = np.random.randn(n_hidden_2).astype(floatX)
init_b_out = np.random.randn(cosine_count*3).astype(floatX)

# Initialize shared
model3_input = pytensor.shared(np.array(X3_train).astype(floatX))
model3_amp_output = pytensor.shared(np.array(Y3_train['amp']).astype(floatX))
model3_wl_output = pytensor.shared(np.array(Y3_train['wl']).astype(floatX))
model3_phase_output = pytensor.shared(np.array(Y3_train['phase']).astype(floatX))
model3_output = pytensor.shared(np.array(Y3_train).astype(floatX))

with pm.Model() as neural_network:
    # Weights from input to hidden layer
    weights_in_1 = pm.Normal('w_in_1', mu=0, sigma=1, shape=(model3_input.shape[1], n_hidden_1), initval=init_1)
    # Bias at 1st hidden layer
    bias_1 = pm.Normal('b_1', mu=0, sigma=1, shape=(n_hidden_1), initval=init_b_1)

    # Weights from 1st to 2nd hidden layer
    weights_1_2 = pm.Normal('w_1_2', mu=0, sigma=1, shape=(n_hidden_1, n_hidden_2), initval=init_2)
    # Bias at 2nd hidden layer
    bias_2 = pm.Normal('b_2', mu=0, sigma=1, shape=(n_hidden_2), initval=init_b_2)

    # Weights from hidden layer to output (3 outputs)
    weights_2_out = pm.Normal('w_2_out', mu=0, sigma=1, shape=(n_hidden_2, 3), initval=init_out)
    # Bias at output hidden layer
    bias_out = pm.Normal('b_out', mu=0, sigma=1, shape=(3), initval=init_b_out)


    # Build neural-network using tanh activation function
    act_1 = pm.math.tanh(pm.math.dot(model3_input, weights_in_1) + bias_1)
    act_2 = pm.math.tanh(pm.math.dot(act_1, weights_1_2) + bias_2)
    #act_out = pm.math.dot(act_2, weights_2_out) + bias_out
    act_out_amp = pm.math.dot(act_2, weights_2_out[:,0]) + bias_out[0]
    act_out_wl = pm.math.dot(act_2, weights_2_out[:,1]) + bias_out[1]
    act_out_phase = pm.math.dot(act_2, weights_2_out[:,2]) + bias_out[2]

    sd_amp = pm.HalfNormal('sd_amp', sigma=1)
    out_amp = pm.Normal('amp', mu=act_out_amp, sigma=sd_amp, observed=model3_amp_output)

    sd_wl = pm.HalfNormal('sd_wl', sigma=1)
    out_wl = pm.Normal('wl', mu=act_out_wl, sigma=sd_wl, observed=model3_wl_output)

    sd_phase = pm.HalfNormal('sd_phase', sigma=1)
    out_phase = pm.Normal('phase', mu=act_out_phase, sigma=sd_phase, observed=model3_phase_output)

with neural_network:
    step = pm.NUTS(target_accept=0.9)
    nn_trace = pm.sample(draws=2_000, tune=1_000, step=step, chains=1, return_inferencedata=True, nuts_sampler="numpyro")

    plt.figure(figsize=(16,9))
    plt.plot(nn_trace, label="NUTS", alpha=0.3)
    #print(az.summary(nn_trace))
    #az.plot_trace(nn_trace, combined=False)
    #plt.show()

    #az.plot_forest(nn_trace)
    #plt.show()

# Replace shared variables with testing set
# Need to set as shapes change when test and training sets differ in shape
model3_input.set_value(np.array(X3_test).astype(floatX))
model3_amp_output.set_value(np.array(Y3_test['amp']).astype(floatX))
model3_wl_output.set_value(np.array(Y3_test['wl']).astype(floatX))
model3_phase_output.set_value(np.array(Y3_test['phase']).astype(floatX))

ppc_nn = pm.sample_posterior_predictive(nn_trace, model=neural_network).posterior_predictive

from src.SymbolicMath import SymAngularMean
pred_amp = np.array(ppc_nn['amp']).mean()
pred_wl = np.array(ppc_nn['wl']).mean()
pred_phase = SymAngularMean(np.array(ppc_nn['phase']))

print("AMP: ", pred_amp, " WL: ", pred_wl, " PHASE: ", pred_phase)

# Plot predicted surface
from src.SymbolicMath import SymCosineSurface

truep = (0.0015, 0.05, 0.0)

x = np.linspace(0, 0.6, 1000)
plt.figure(figsize=(16,9))
plt.plot(x, SymCosineSurface(x, (pred_amp, pred_wl, pred_phase)), label='mean predicted surface')
plt.plot(x, SymCosineSurface(x, truep), label='true surface')
plt.legend()
plt.show()

import corner
corner.corner(np.array((np.array(ppc_nn['amp']),np.array(ppc_nn['wl']),np.array(ppc_nn['phase']))),bins=200,
            quantiles=[0.16, 0.5, 0.84],labels=[r"$\zeta_1$", r"$\zeta_2$", r"$\zeta_3$"],
            show_titles=True, title_fmt = ".4f")
plt.savefig("results/nn_corner.png")
plt.show()

import pypsa
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use("bmh")


#       Read and Prepare Data
#       Cost Data
def annuity(r, n):
    return r / (1.0 - 1.0 / (1.0 + r) ** n)


year = 2030
url = f"https://raw.githubusercontent.com/PyPSA/technology-data/master/outputs/costs_{year}.csv"
costs = pd.read_csv(url, index_col=[0, 1])

costs.loc[costs.unit.str.contains("/kW"), "value"] *= 1e3
costs.unit = costs.unit.str.replace("/kW", "/MW")

defaults = {
    "FOM": 0,
    "VOM": 0,
    "efficiency": 1,
    "fuel": 0,
    "investment": 0,
    "lifetime": 25,
    "CO2 intensity": 0,
    "discount rate": 0.07,
}
costs = costs.value.unstack().fillna(defaults)

costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]
costs.at["CCGT", "fuel"] = costs.at["gas", "fuel"]
costs.at["OCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]
costs.at["CCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]

costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]
annuity_values = costs.apply(
    lambda costs_row: annuity(costs_row["discount rate"], costs_row["lifetime"]), axis=1
)
costs["capital_cost"] = (annuity_values + costs["FOM"] / 100) * costs["investment"]
print(costs)

#       Load Data
url = (
    "https://tubcloud.tu-berlin.de/s/pKttFadrbTKSJKF/download/time-series-lecture-2.csv"
)
ts = pd.read_csv(url, index_col=0, parse_dates=True)
ts.load *= 1e3  # Convert GW to MW
resolution = 4  # hr
ts = ts.resample(f"{resolution}h").first()
print(ts)


#       Build the Model:
n = pypsa.Network()

n.add("Bus", "electricity")

n.set_snapshots(ts.index)
n.snapshot_weightings[:] = resolution

carriers = [
    "onwind",
    "offwind",
    "solar",
    "OCGT",
    "hydrogen storage underground",
    "battery storage",
]
n.add(
    "Carrier",
    carriers,
    color=["dodgerblue", "aquamarine", "gold", "indianred", "magenta", "yellowgreen"],
    co2_emissions=[costs.at[carrier, "CO2 intensity"] for carrier in carriers],
)

n.add(
    "Load",
    "demand",
    bus="electricity",
    p_set=ts.load,
)
# n.loads_t.p_set.plot()
# plt.show()

n.add(
    "Generator",
    "OCGT",
    bus="electricity",
    carrier="OCGT",
    capital_cost=costs.at["OCGT", "capital_cost"],
    marginal_cost=costs.at["OCGT", "marginal_cost"],
    efficiency=costs.at["OCGT", "efficiency"],
    p_nom_extendable=True,
)

for tech in ["onwind", "offwind", "solar"]:
    n.add(
        "Generator",
        tech,
        carrier=tech,
        bus="electricity",
        capital_cost=costs.at[tech, "capital_cost"],
        marginal_cost=costs.at[tech, "marginal_cost"],
        efficiency=costs.at[tech, "efficiency"],
        p_max_pu=ts[tech],
        p_nom_extendable=True,
    )
print(n.generators)
# n.generators_t.p_max_pu.loc["2015-03"].plot()
# plt.show()

#       Optimize
n.optimize()

print(f"Objective = {n.objective/1.0e9}")  # Billion Euros
print(f"Optimized Cpacities: {n.generators.p_nom_opt}")  # MW

emissions = (
    n.generators_t.p
    / n.generators.efficiency
    * n.generators.carrier.map(n.carriers.co2_emissions)
) # t/h

total_emissions = n.snapshot_weightings.generators @ emissions.sum(axis=1)/1e6 # Mt
print(f"Total emissions={total_emissions}")

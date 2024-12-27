import pypsa
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use("bmh")


#       Helper Functions:
def annuity(r, n):
    return r / (1.0 - 1.0 / (1.0 + r) ** n)


def CalculateTotalEmissions(net):  # Mt
    emissions = (
        net.generators_t.p
        / net.generators.efficiency
        * net.generators.carrier.map(net.carriers.co2_emissions)
    )  # t/h
    total_emissions = net.snapshot_weightings.generators @ emissions.sum(axis=1) / 1e6
    return total_emissions


def GetSystemCost(net):
    totalSystemCost = pd.concat([net.statistics.capex(), net.statistics.opex()], axis=1)
    return (
        totalSystemCost.sum(axis=1).droplevel(0).div(1e9).round(2)
    )  # billion euros/year


def PrintCEMResults(net):
    print("--- Optimization Results ---")
    print(f"Objective = {net.objective/1.0e9}")  # Billion Euros
    print(f"Optimized Cpacities:")  # MW
    print(n.generators.p_nom_opt)
    print(n.storage_units.p_nom_opt)
    print(f"Total emissions = {CalculateTotalEmissions(net)}")
    print("System Costs:")
    print(GetSystemCost(n))
    print(40 * "-")


#       Read and Prepare Data
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

n.optimize()

PrintCEMResults(n)

#       Storage Units:
n.add(
    "StorageUnit",
    "battery storage",
    bus="electricity",
    carrier="battery storage",
    max_hours=6,
    capital_cost=costs.at["battery inverter", "capital_cost"]
    + 6 * costs.at["battery storage", "capital_cost"],
    efficieny_storage=costs.at["battery inverter", "efficiency"],
    efficieny_dispatch=costs.at["battery inverter", "efficiency"],
    cyclic_state_of_charge=True,
    p_nom_extendable=True,
)

H2_str_max_hours = 168
H2_str_capital_cost = (
    costs.at["electrolysis", "capital_cost"]
    + costs.at["fuel cell", "capital_cost"]
    + H2_str_max_hours * costs.at["hydrogen storage underground", "capital_cost"]
)

n.add(
    "StorageUnit",
    "hydrogen storage underground",
    bus="electricity",
    carrier="hydrogen storage underground",
    max_hours=H2_str_max_hours,
    capital_cost=H2_str_capital_cost,
    efficiency_storage=costs.at["electrolysis", "efficiency"],
    efficiency_dispatch=costs.at["fuel cell", "efficiency"],
    p_nom_extendable=True,
    cyclic_state_of_charge=True,
)

n.optimize()

PrintCEMResults(n)


#       Emission Limit:
n.add(
    "GlobalConstraint",
    "CO2Limit",
    carrier_attribute="co2_emissions",
    sense="<=",
    constant=0,
)

n.optimize()

PrintCEMResults(n)

GetSystemCost(n).plot.pie()
#plt.show()
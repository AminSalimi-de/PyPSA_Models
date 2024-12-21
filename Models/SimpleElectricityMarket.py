import pypsa

#   Parameters
#       Euro/MWh
fuel_cost = dict(coal=8, gas=100, oil=48)

#       For Thermal Power Plants
efficiency = dict(coal=0.33, gas=0.58, oil=0.35)

#       t/MWh
emissions = dict(coal=0.34, gas=0.2, oil=0.26, hydro=0, wind=0)

#       Power Plants Capacities (MW)
power_plants = {
    "SA": {"coal": 35000, "wind": 3000, "gas": 8000, "oil": 2000},
    "MZ": {"hydro": 1200}
}

#       MW
loads = {"SA": 42000, "MZ": 650}


#   Model:
n = pypsa.Network()

#       Buses:
n.add("Bus", "SA", y=-30.5, x=25, v_nom=400, carrier="AC")
n.add("Bus", "MZ", y=-18.5, x=35.5, v_nom=400, carrier="AC")
print(n.buses)

#       Carriers:
n.add(
    "Carrier",
    ["coal", "gas", "oil", "hydro", "wind"],
    co2_emissions=emissions,
    nice_name=["Coal", "Gas", "Oil", "Hydro", "Onshore Wind"],
    color=["grey", "indianred", "black", "aquamarine", "dodgerblue"],
)
n.add("Carrier", ["electricity", "AC"])
print(n.carriers)

#       Generators:
n.add(
    "Generator",
    "MZ hydro",
    bus="MZ",
    carrier="hydro",
    p_nom=1200,  # MW
    mariginal_cost=0,
)
for tech, capacity in power_plants["SA"].items():
    n.add(
        "Generator",
        f"SA {tech}",
        bus="SA",
        carrier=tech,
        efficiency=efficiency.get(tech, 1),
        mariginal_cost=fuel_cost.get(tech, 0)/efficiency.get(tech, 1),
        p_nom=capacity
    )
print(n.generators)

#       Demands:
n.add(
    "Load",
    "SA electricity demand",
    bus="SA",
    carrier="electricity",
    p_set=loads["SA"]
)
n.add(
    "Load",
    "MZ electricity demand",
    bus="MZ",
    carrier="electricity",
    p_set=loads["MZ"]
)
print(n.loads)

#       Lines:
n.add(
    "Line",
    "SA-MZ",
    bus0="SA",
    bus1="MZ",
    s_nom=500,
    x=1,
    r=1
)
print(n.lines)

#       Plot Network:
n.plot(bus_sizes=1, margin=1)
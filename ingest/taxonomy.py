"""Our risk taxonomy and how GDELT GKG themes map onto it.

Each risk type lists exact GKG theme names. Theme names were checked against
GDELT's LOOKUP-GKGTHEMES.TXT.
"""

CATEGORIES = {
    "natural": "Natural hazards",
    "industrial": "Industrial incidents",
    "labour": "Labour & unrest",
    "operations": "Operations",
    "logistics": "Logistics",
    "geopolitical": "Geopolitical & trade",
    "financial": "Financial",
    "cyber": "Cyber",
    "esg": "ESG & human rights",
    "health": "Health",
}

_ND = "NATURAL_DISASTER_"
_MD = "MANMADE_DISASTER_"

# code: (category, label, [GKG themes])
RISK_TYPES = {
    "flood": ("natural", "Flood / heavy rain", [_ND + s for s in (
        "FLOOD", "FLOODING", "FLOODS", "FLOODED", "FLOODWATERS", "HEAVY_RAIN", "HEAVY_RAINS")]),
    "earthquake": ("natural", "Earthquake / tsunami", [_ND + s for s in (
        "EARTHQUAKE", "EARTHQUAKES", "TREMORS", "TSUNAMI")]),
    "storm": ("natural", "Storm / cyclone", [_ND + s for s in (
        "HURRICANE", "HURRICANES", "TYPHOON", "CYCLONE", "TROPICAL_STORM", "TORNADO", "TORNADOES",
        "STRONG_WINDS", "HIGH_WINDS", "SEVERE_WEATHER", "EXTREME_WEATHER", "BLIZZARD", "MONSOON")]),
    "wildfire": ("natural", "Wildfire", [_ND + s for s in ("WILDFIRE", "WILDFIRES", "FOREST_FIRES")]),
    "drought_heat": ("natural", "Drought / heat / water stress", [
        _ND + "DROUGHT", _ND + "HEAT_WAVE", "WATER_SECURITY"]),
    "landslide": ("natural", "Landslide", [_ND + "LANDSLIDE", _ND + "LANDSLIDES"]),
    "volcano": ("natural", "Volcano", [_ND + s for s in ("VOLCANO", "VOLCANIC", "ERUPTION")]),

    "fire": ("industrial", "Fire", ["DISASTER_FIRE", _MD + "CHEMICAL_FIRE"]),
    "explosion": ("industrial", "Explosion", [_MD + "GAS_EXPLOSION"]),
    "chemical": ("industrial", "Chemical / toxic / oil spill", [_MD + s for s in (
        "CHEMICAL_SPILL", "TOXIC_WASTE", "TOXIC_SUBSTANCE", "TOXIC_SPILL", "TOXIC_LEAK", "OIL_SPILL")]),
    "industrial_accident": ("industrial", "Industrial / workplace accident", [
        _MD + "INDUSTRIAL_ACCIDENT", _MD + "INDUSTRIAL_DISASTER", "UNSAFE_WORK_ENVIRONMENT"]),

    "strike": ("labour", "Strike", ["STRIKE", "TAX_FNCACT_STRIKER", "TAX_FNCACT_STRIKERS"]),
    "protest": ("labour", "Protest / civil unrest", ["PROTEST", "VIOLENT_UNREST"]),

    "shortage": ("operations", "Shortage", ["SHORTAGE"]),
    "closure": ("operations", "Closure / shutdown", ["CLOSURE"]),
    "power_outage": ("operations", "Power outage", [
        "POWER_OUTAGE", _MD + "POWER_OUTAGES", _MD + "WITHOUT_POWER"]),

    "blockade": ("logistics", "Blockade", ["BLOCKADE"]),
    "ports": ("logistics", "Ports", ["WB_167_PORTS"]),

    "sanctions": ("geopolitical", "Sanctions", ["SANCTIONS"]),
    "trade_dispute": ("geopolitical", "Trade dispute", ["ECON_TRADE_DISPUTE"]),
    "nationalization": ("geopolitical", "Nationalization", ["ECON_NATIONALIZE"]),

    "bankruptcy": ("financial", "Bankruptcy", ["ECON_BANKRUPTCY"]),
    "outlook_cut": ("financial", "Outlook cut", ["ECON_CUTOUTLOOK"]),

    "cyber_attack": ("cyber", "Cyber attack", ["CYBER_ATTACK"]),

    "forced_labour": ("esg", "Forced labour / slavery", ["WB_1669_FORCED_LABOR", "SOC_SLAVERY"]),
    "child_labour": ("esg", "Child labour", ["WB_1859_CHILD_LABOR"]),
    "trafficking": ("esg", "Human trafficking", ["HUMAN_TRAFFICKING"]),
    "human_rights": ("esg", "Human rights abuses", ["HUMAN_RIGHTS_ABUSES"]),
    "deforestation": ("esg", "Deforestation", ["ENV_DEFORESTATION"]),
    "corruption": ("esg", "Corruption", ["CORRUPTION"]),

    "outbreak": ("health", "Disease outbreak", [
        "TAX_DISEASE_OUTBREAK", "TAX_DISEASE_EPIDEMIC", "SOC_QUARANTINE"]),
}

THEME_TO_RISK = {theme: code for code, (_, _, themes) in RISK_TYPES.items() for theme in themes}


def as_json():
    return {
        "categories": [{"code": c, "label": l} for c, l in CATEGORIES.items()],
        "riskTypes": [
            {"code": code, "category": cat, "label": label, "gdeltThemes": themes}
            for code, (cat, label, themes) in RISK_TYPES.items()
        ],
    }

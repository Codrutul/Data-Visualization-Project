import json
import os
import random
import math
from datetime import datetime, timedelta

def main():
    data_dir = r"c:\Users\afloa\OneDrive\Desktop\data visualization mock\data"
    os.makedirs(data_dir, exist_ok=True)

    # 1. dc-count-by-country.json
    base_countries = {
        "USA": 5381, "GBR": 456, "DEU": 522, "CHN": 449, "CAN": 328, "AUS": 306, 
        "FRA": 310, "NLD": 281, "JPN": 219, "IND": 183, "BRA": 155, "RUS": 120, 
        "SGP": 100, "KOR": 95, "HKG": 85, "ITA": 80, "ESP": 75, "CHE": 70, 
        "SWE": 65, "POL": 55
    }
    other_iso = ["MEX", "ZAF", "IRL", "TUR", "CHL", "MYS", "IDN", "ARE", "ARG", "COL", 
                 "THA", "VNM", "PHL", "NGA", "EGY", "SAU", "ISR", "NOR", "DNK", "FIN",
                 "NZL", "BEL", "AUT", "PRT", "GRC", "CZE", "HUN", "ROU", "BGR", "HRV",
                 "SRB", "SVK", "SVN", "EST", "LVA", "LTU", "ISL", "LUX", "CYP", "MLT"]
    for idx, iso in enumerate(other_iso):
        base_countries[iso] = max(5, 50 - int(idx * 1.1))
    
    with open(os.path.join(data_dir, "dc-count-by-country.json"), "w") as f:
        json.dump(base_countries, f, indent=2)

    # 2. dc-count-by-state.json
    states = {
        "VA": 498, "TX": 413, "CA": 387, "IL": 144, "NY": 138, "OR": 110, "OH": 105, 
        "GA": 95, "AZ": 92, "WA": 88, "NJ": 85, "FL": 80, "NC": 78, "PA": 72, "CO": 65, 
        "NV": 60, "UT": 55, "MN": 50, "MD": 48, "SC": 45, "MA": 42, "MO": 38, "IA": 35, 
        "WI": 32, "TN": 30, "MI": 28, "IN": 25, "KY": 22, "AL": 20, "LA": 18, "CT": 16, 
        "NE": 15, "KS": 14, "OK": 13, "NH": 12, "NM": 10, "ID": 9, "MS": 8, "AR": 7, 
        "RI": 6, "ME": 5, "WV": 4, "MT": 4, "SD": 3, "ND": 3, "VT": 3, "WY": 2, "AK": 2, 
        "HI": 2, "DE": 8, "DC": 15
    }
    with open(os.path.join(data_dir, "dc-count-by-state.json"), "w") as f:
        json.dump(states, f, indent=2)

    # 3. dc-locations-sample.json
    locations = []
    # US Hubs
    hubs = [
        {"name": "Ashburn VA", "lat": 39.0438, "lng": -77.4874, "state": "VA", "country": "USA", "count": 20},
        {"name": "Dallas TX", "lat": 32.7767, "lng": -96.7970, "state": "TX", "country": "USA", "count": 15},
        {"name": "Santa Clara CA", "lat": 37.3541, "lng": -121.9552, "state": "CA", "country": "USA", "count": 15},
        {"name": "Chicago IL", "lat": 41.8781, "lng": -87.6298, "state": "IL", "country": "USA", "count": 8},
        {"name": "Hillsboro OR", "lat": 45.5229, "lng": -122.9898, "state": "OR", "country": "USA", "count": 8},
        {"name": "Phoenix AZ", "lat": 33.4484, "lng": -112.0740, "state": "AZ", "country": "USA", "count": 10},
        {"name": "Atlanta GA", "lat": 33.7490, "lng": -84.3880, "state": "GA", "country": "USA", "count": 10},
        {"name": "New York NY", "lat": 40.7128, "lng": -74.0060, "state": "NY", "country": "USA", "count": 14}
    ]
    # Int Hubs
    int_hubs = [
        {"name": "London", "lat": 51.5074, "lng": -0.1278, "country": "GBR", "count": 15},
        {"name": "Frankfurt", "lat": 50.1109, "lng": 8.6821, "country": "DEU", "count": 15},
        {"name": "Amsterdam", "lat": 52.3676, "lng": 4.9041, "country": "NLD", "count": 15},
        {"name": "Singapore", "lat": 1.3521, "lng": 103.8198, "country": "SGP", "count": 12},
        {"name": "Tokyo", "lat": 35.6762, "lng": 139.6503, "country": "JPN", "count": 10},
        {"name": "Sydney", "lat": -33.8688, "lng": 151.2093, "country": "AUS", "count": 10},
        {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777, "country": "IND", "count": 8},
        {"name": "Sao Paulo", "lat": -23.5505, "lng": -46.6333, "country": "BRA", "count": 8},
        {"name": "Paris", "lat": 48.8566, "lng": 2.3522, "country": "FRA", "count": 7}
    ]
    operators = ["Equinix", "Digital Realty", "CyrusOne", "QTS", "NTT", "AWS", "Google", "Microsoft", "Meta", "CoreSite", "Vantage", "DataBank"]
    
    for h in hubs + int_hubs:
        for i in range(h["count"]):
            loc = {
                "lat": h["lat"] + (random.random() - 0.5) * 0.1,
                "lng": h["lng"] + (random.random() - 0.5) * 0.1,
                "name": f"{h['name']}{i+1}",
                "operator": random.choice(operators),
                "country": h["country"]
            }
            if "state" in h:
                loc["state"] = h["state"]
            locations.append(loc)
            
    with open(os.path.join(data_dir, "dc-locations-sample.json"), "w") as f:
        json.dump(locations, f, indent=2)

    # 4. grid-regions.json
    grids = [
        {"name": "PJM Interconnection", "abbr": "PJM", "states": ["VA", "MD", "PA", "NJ", "DE", "OH", "WV", "IN", "IL", "KY", "MI", "NC", "TN", "DC"], "demand_twh": 800, "peak_demand_gw": 150, "dc_load_share_pct": 8.5, "carbon_intensity_lb_co2_mwh": 820, "color": "#3b82f6", "center": [39.5, -77.5]},
        {"name": "Midcontinent ISO", "abbr": "MISO", "states": ["MN", "IA", "MO", "AR", "LA", "MS", "ND", "SD", "WI", "MI", "IL", "IN", "KY", "TX"], "demand_twh": 650, "peak_demand_gw": 120, "dc_load_share_pct": 4.2, "carbon_intensity_lb_co2_mwh": 1050, "color": "#ef4444", "center": [42.0, -93.0]},
        {"name": "Electric Reliability Council of Texas", "abbr": "ERCOT", "states": ["TX"], "demand_twh": 430, "peak_demand_gw": 85, "dc_load_share_pct": 6.8, "carbon_intensity_lb_co2_mwh": 790, "color": "#f59e0b", "center": [31.0, -99.0]},
        {"name": "California ISO", "abbr": "CAISO", "states": ["CA", "NV"], "demand_twh": 250, "peak_demand_gw": 45, "dc_load_share_pct": 5.5, "carbon_intensity_lb_co2_mwh": 450, "color": "#10b981", "center": [36.0, -119.0]},
        {"name": "Southwest Power Pool", "abbr": "SPP", "states": ["KS", "OK", "NE", "ND", "SD", "MO", "NM", "TX"], "demand_twh": 280, "peak_demand_gw": 55, "dc_load_share_pct": 3.1, "carbon_intensity_lb_co2_mwh": 890, "color": "#8b5cf6", "center": [38.0, -98.0]},
        {"name": "New York ISO", "abbr": "NYISO", "states": ["NY"], "demand_twh": 160, "peak_demand_gw": 32, "dc_load_share_pct": 4.5, "carbon_intensity_lb_co2_mwh": 350, "color": "#ec4899", "center": [43.0, -75.0]},
        {"name": "ISO New England", "abbr": "ISO-NE", "states": ["ME", "NH", "VT", "MA", "CT", "RI"], "demand_twh": 120, "peak_demand_gw": 25, "dc_load_share_pct": 3.0, "carbon_intensity_lb_co2_mwh": 410, "color": "#06b6d4", "center": [43.0, -71.0]},
        {"name": "Southeast (SERC)", "abbr": "SERC", "states": ["AL", "GA", "SC", "NC", "TN", "MS", "FL"], "demand_twh": 950, "peak_demand_gw": 180, "dc_load_share_pct": 7.0, "carbon_intensity_lb_co2_mwh": 910, "color": "#f97316", "center": [33.0, -83.0]},
        {"name": "Northwest (NWPP)", "abbr": "NWPP", "states": ["WA", "OR", "ID", "MT", "WY", "UT"], "demand_twh": 310, "peak_demand_gw": 60, "dc_load_share_pct": 9.5, "carbon_intensity_lb_co2_mwh": 250, "color": "#14b8a6", "center": [45.0, -119.0]},
        {"name": "Southwest (SWPP)", "abbr": "SWPP", "states": ["AZ", "NM", "CO"], "demand_twh": 200, "peak_demand_gw": 40, "dc_load_share_pct": 5.0, "carbon_intensity_lb_co2_mwh": 760, "color": "#6366f1", "center": [34.0, -111.0]}
    ]
    with open(os.path.join(data_dir, "grid-regions.json"), "w") as f:
        json.dump(grids, f, indent=2)

    # 5. water-stress-by-state.json
    water = {}
    stress_mapping = {
        "AZ": 4.8, "NM": 4.5, "NV": 4.2, "CA": 3.9, "UT": 3.7, "CO": 3.2, "TX": 3.0, "KS": 2.8, "OK": 2.5, "NE": 2.3,
        "VA": 1.5, "NY": 0.8
    }
    for st, count in states.items():
        score = stress_mapping.get(st, random.uniform(0.1, 2.2))
        cat = "Low"
        if score > 4: cat = "Extremely High"
        elif score > 3: cat = "High"
        elif score > 2: cat = "Medium-High"
        elif score > 1: cat = "Low-Medium"
        water[st] = {
            "stress_score": round(score, 1),
            "category": cat,
            "dc_water_mgd": round((count / 500.0) * 15.0, 1) # simple mapping based on count
        }
    with open(os.path.join(data_dir, "water-stress-by-state.json"), "w") as f:
        json.dump(water, f, indent=2)

    # 6. market-caps.json
    market_caps = []
    # ~92 months from Jan 2019 to Aug 2026
    start_date = datetime(2019, 1, 1)
    # Define roughly trajectories
    def interp(date, pts):
        # pts: list of (year, val)
        t = date.year + (date.month-1)/12.0
        for i in range(len(pts)-1):
            if pts[i][0] <= t <= pts[i+1][0]:
                frac = (t - pts[i][0]) / (pts[i+1][0] - pts[i][0])
                return pts[i][1] + frac * (pts[i+1][1] - pts[i][1])
        return pts[-1][1]

    pts_nvda = [(2019, 83), (2020, 145), (2021.5, 360), (2023, 300), (2023.8, 1200), (2024.5, 2000), (2025.2, 3200), (2026.5, 3800)]
    pts_msft = [(2019, 789), (2021, 1600), (2023, 1800), (2024.5, 2800), (2025, 3300), (2026.5, 3600)]
    pts_googl = [(2019, 726), (2021, 1200), (2023, 1300), (2024.5, 2100), (2025, 2400), (2026.5, 2600)]
    pts_amzn = [(2019, 797), (2021, 1650), (2022.5, 850), (2024, 1550), (2025, 2200), (2026.5, 2400)]
    pts_meta = [(2019, 375), (2021, 920), (2022.8, 270), (2024, 900), (2025, 1500), (2026.5, 1700)]

    for m in range(92):
        d = start_date.replace(month=(m % 12) + 1, year=start_date.year + m // 12)
        # Add a bit of noise
        noise = random.uniform(0.95, 1.05)
        market_caps.append({
            "date": d.strftime("%Y-%m"),
            "NVDA": round(interp(d, pts_nvda) * noise),
            "MSFT": round(interp(d, pts_msft) * noise),
            "GOOGL": round(interp(d, pts_googl) * noise),
            "AMZN": round(interp(d, pts_amzn) * noise),
            "META": round(interp(d, pts_meta) * noise)
        })
    with open(os.path.join(data_dir, "market-caps.json"), "w") as f:
        json.dump(market_caps, f, indent=2)

    # 7. openai-valuation.json
    openai = [
        {"date": "2019-07", "valuation": 4, "event": "Microsoft $1B partnership"},
        {"date": "2023-01", "valuation": 29, "event": "Microsoft $10B investment"},
        {"date": "2023-10", "valuation": 86, "event": "Thrive Capital tender offer"},
        {"date": "2024-10", "valuation": 157, "event": "$6.6B funding round"},
        {"date": "2025-03", "valuation": 300, "event": "SoftBank $40B round"},
        {"date": "2025-10", "valuation": 500, "event": "Employee liquidity tender"},
        {"date": "2026-03", "valuation": 852, "event": "$122B mega-round"}
    ]
    with open(os.path.join(data_dir, "openai-valuation.json"), "w") as f:
        json.dump(openai, f, indent=2)

    # 8. hyperscale-growth.json
    hyper = [
        {"year": 2015, "total": 259, "us_pct": 45, "eu_pct": 20, "apac_pct": 25, "other_pct": 10},
        {"year": 2016, "total": 320, "us_pct": 44, "eu_pct": 21, "apac_pct": 25, "other_pct": 10},
        {"year": 2017, "total": 390, "us_pct": 43, "eu_pct": 21, "apac_pct": 26, "other_pct": 10},
        {"year": 2018, "total": 440, "us_pct": 42, "eu_pct": 22, "apac_pct": 26, "other_pct": 10},
        {"year": 2019, "total": 504, "us_pct": 41, "eu_pct": 22, "apac_pct": 27, "other_pct": 10},
        {"year": 2020, "total": 600, "us_pct": 40, "eu_pct": 22, "apac_pct": 28, "other_pct": 10},
        {"year": 2021, "total": 700, "us_pct": 39, "eu_pct": 23, "apac_pct": 28, "other_pct": 10},
        {"year": 2022, "total": 850, "us_pct": 39, "eu_pct": 23, "apac_pct": 28, "other_pct": 10},
        {"year": 2023, "total": 992, "us_pct": 39, "eu_pct": 23, "apac_pct": 28, "other_pct": 10},
        {"year": 2024, "total": 1136, "us_pct": 40, "eu_pct": 22, "apac_pct": 28, "other_pct": 10},
        {"year": 2025, "total": 1360, "us_pct": 41, "eu_pct": 22, "apac_pct": 27, "other_pct": 10},
        {"year": 2026, "total": 1580, "us_pct": 42, "eu_pct": 21, "apac_pct": 27, "other_pct": 10}
    ]
    with open(os.path.join(data_dir, "hyperscale-growth.json"), "w") as f:
        json.dump(hyper, f, indent=2)

    # 9. key-events.json
    events = [
        {"date": "2020-03", "label": "COVID-19 Pandemic", "type": "market"},
        {"date": "2022-11", "label": "ChatGPT Launch", "type": "ai"},
        {"date": "2023-05", "label": "NVIDIA Earnings Surge", "type": "ai"},
        {"date": "2024-01", "label": "GPT-4 Turbo & AI Arms Race", "type": "ai"},
        {"date": "2024-06", "label": "NVIDIA Passes $3T Market Cap", "type": "market"},
        {"date": "2025-01", "label": "Stargate $500B AI Infrastructure Plan", "type": "infra"},
        {"date": "2025-06", "label": "US Data Center Electricity 6% of Grid", "type": "infra"}
    ]
    with open(os.path.join(data_dir, "key-events.json"), "w") as f:
        json.dump(events, f, indent=2)

if __name__ == '__main__':
    main()

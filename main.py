import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from stadium_locations import STADIUM_COORDS
from stat_rules import apply_sensitivity

load_dotenv()
API_KEY = os.getenv("OWM_API_KEY")

def get_forecast(lat, lon, match_datetime):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        closest_forecast = None
        min_diff = timedelta(hours=3)

        for entry in data["list"]:
            forecast_time = datetime.strptime(entry["dt_txt"], "%Y-%m-%d %H:%M:%S")
            time_diff = abs(match_datetime - forecast_time)

            if time_diff < min_diff:
                min_diff = time_diff
                closest_forecast = entry

        if closest_forecast:
            return {
                "rain": closest_forecast.get("rain", {}).get("3h", 0),
                "wind_speed": closest_forecast["wind"]["speed"],
                "humidity": closest_forecast["main"]["humidity"]
            }

        return None

    except Exception as e:
        print(f"Error fetching forecast: {e}")
        return None

# --- Sample Round Fixture ---
ROUND_FIXTURE = [
    {"match": "Collingwood vs Carlton", "stadium": "MCG", "datetime": datetime(2025, 5, 10, 19, 20)},
    {"match": "Suns vs Bombers", "stadium": "Marvel Stadium", "datetime": datetime(2025, 5, 11, 13, 45)},
    # Add more matches here...
]

# --- Run Forecast & Sensitivity Table ---
def run_summary():
    print(f"{'Match':<35} | Rain | Wind | Humid | Marks | Goals | Tackles | Rating")
    print("-" * 95)

    for game in ROUND_FIXTURE:
        lat, lon = STADIUM_COORDS[game["stadium"]]
        forecast = get_forecast(lat, lon, game["datetime"])

        if forecast:
            adjustments = apply_sensitivity(
                rain=forecast["rain"],
                wind=forecast["wind_speed"],
                humidity=forecast["humidity"]
            )

            print(f"{game['match']:<35} | "
                  f"{forecast['rain']:>4.1f} | "
                  f"{forecast['wind_speed']:>4.1f} | "
                  f"{forecast['humidity']:>5}% | "
                  f"{adjustments['marks_adj']:>6} | "
                  f"{adjustments['goals_adj']:>6} | "
                  f"{adjustments['tackles_adj']:>8} | "
                  f"{adjustments['rating']}")
        else:
            print(f"{game['match']:<35} | ❌ No forecast data")

if __name__ == "__main__":
    run_summary()

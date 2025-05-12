import requests
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
from math import radians, cos, sin, asin, sqrt
from stadium_locations import STADIUM_COORDS

# Home venues for travel reference
TEAM_HOME_VENUE = {
    "Adelaide Crows": "Adelaide Oval",
    "Port Adelaide": "Adelaide Oval",
    "West Coast Eagles": "Optus Stadium",
    "Fremantle": "Optus Stadium",
    "Brisbane Lions": "Gabba",
    "Gold Coast SUNS": "Heritage Bank Stadium",
    "Sydney Swans": "SCG",
    "GWS Giants": "Giants Stadium",
    "North Melbourne": "Marvel Stadium",
    "Essendon": "Marvel Stadium",
    "Carlton": "Marvel Stadium",
    "Collingwood": "MCG",
    "Hawthorn": "MCG",
    "Melbourne": "MCG",
    "Richmond": "MCG",
    "St Kilda": "Marvel Stadium",
    "Western Bulldogs": "Marvel Stadium",
    "Geelong Cats": "GMHBA Stadium"
}

def fetch_full_fixture():
    url = "https://fixturedownload.com/feed/json/afl-2025"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def haversine(coord1, coord2):
    lon1, lat1 = coord1[1], coord1[0]
    lon2, lat2 = coord2[1], coord2[0]
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

def timezone_offset(lat):
    if lat < -40: return 10
    elif lat < -33: return 10.5 if lat > -35 else 8
    else: return 10

def is_real_travel(venue1, venue2):
    if not venue1 or not venue2:
        return False
    city_groups = [
        {"MCG", "Marvel Stadium", "GMHBA Stadium", "Mars Stadium"},
        {"SCG", "Giants Stadium"},
        {"Gabba", "Heritage Bank Stadium"},
        {"Blundstone Arena", "University of Tasmania Stadium"},
    ]
    for group in city_groups:
        if venue1 in group and venue2 in group:
            return False
    return True

def is_home_game(team, venue):
    home_venue = TEAM_HOME_VENUE.get(team)
    if not home_venue:
        return False
    return not is_real_travel(home_venue, venue)

def build_travel_log():
    fixture = fetch_full_fixture()
    melb_tz = pytz.timezone('Australia/Melbourne')

    team_matches = defaultdict(list)

    for game in fixture:
        try:
            utc_dt = datetime.strptime(game['DateUtc'], "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=pytz.utc)
            local_dt = utc_dt.astimezone(melb_tz)
            venue = game.get('Location', 'Unknown')

            for team in [game['HomeTeam'], game['AwayTeam']]:
                team_matches[team].append({
                    'opponent': game['AwayTeam'] if team == game['HomeTeam'] else game['HomeTeam'],
                    'datetime': local_dt,
                    'venue': venue,
                    'round': game.get('RoundNumber', -1)
                })
        except Exception as e:
            print(f"Skipping match due to error: {e}")

    for team in team_matches:
        team_matches[team].sort(key=lambda x: x['datetime'])

    travel_log = []

    for team, matches in team_matches.items():
        last_venue = None
        last_time = None
        last_week_real_travel = False

        for match in matches:
            venue = match['venue']
            dt = match['datetime']
            latlon = STADIUM_COORDS.get(venue)

            if not latlon:
                match.update({
                    'team': team,
                    'distance_km': None,
                    'short_rest': None,
                    'back_to_back_travel': None,
                    'timezone_change': None,
                    'fatigue_score': None,
                    'notes': f"Manual Check Required: Unknown venue '{venue}'"
                })
                travel_log.append(match)
                last_venue = venue
                last_time = dt
                last_week_real_travel = False
                continue

            distance = 0
            short_rest = False
            timezone_change = False
            this_week_real_travel = not is_home_game(team, venue)

            if last_venue and STADIUM_COORDS.get(last_venue):
                prev_coords = STADIUM_COORDS.get(last_venue)
                if this_week_real_travel:
                    distance = haversine(prev_coords, latlon)
                    timezone_change = abs(
                        timezone_offset(prev_coords[0]) - timezone_offset(latlon[0])
                    ) >= 2

                if last_time:
                    days_rest = (dt - last_time).days
                    short_rest = days_rest < 6

            back_to_back_travel = last_week_real_travel and this_week_real_travel

            fatigue_score = 0
            notes = []

            if distance > 1500:
                fatigue_score += 1
                notes.append("Long travel")
            if short_rest:
                fatigue_score += 1
                notes.append("Short rest")
            if back_to_back_travel:
                fatigue_score += 1
                notes.append("Back-to-back travel")
            if timezone_change:
                fatigue_score += 1
                notes.append("Time zone shift")

            match.update({
                'team': team,
                'distance_km': round(distance, 1),
                'short_rest': short_rest,
                'back_to_back_travel': back_to_back_travel,
                'timezone_change': timezone_change,
                'fatigue_score': fatigue_score,
                'notes': "; ".join(notes)
            })

            last_venue = venue
            last_time = dt
            last_week_real_travel = this_week_real_travel

            travel_log.append(match)

    return travel_log

# CLI Preview
if __name__ == "__main__":
    log = build_travel_log()
    print(f"\n{'Team':<15} {'Round':<5} {'Opponent':<15} {'Venue':<25} {'Fatigue':<7} {'Notes'}")
    print("-" * 95)
    for entry in log:
        fat_score = entry['fatigue_score']
        fat_display = f"{fat_score}" if fat_score is not None else "N/A"
        print(f"{entry['team']:<15} {entry['round']:<5} {entry['opponent']:<15} {entry['venue']:<25} {fat_display:<7} {entry['notes']}")

import requests
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
from math import radians, cos, sin, asin, sqrt
from stadium_locations import STADIUM_COORDS

# Load all fixture data from the AFL feed
def fetch_full_fixture():
    url = "https://fixturedownload.com/feed/json/afl-2025"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Calculate haversine distance between two (lat, lon) points
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

# Return rough UTC offset estimate
def timezone_offset(lat):
    if lat < -40: return 10  # TAS
    elif lat < -33: return 10.5 if lat > -35 else 8  # SA or WA
    else: return 10  # VIC, QLD, NSW

# Determine whether travel is significant
def is_real_travel(venue1, venue2):
    if not venue1 or not venue2:
        return False
    city_groups = [
        {"MCG", "Marvel Stadium", "GMHBA Stadium", "Mars Stadium"},  # VIC
        {"SCG", "Giants Stadium"},  # Sydney
        {"Gabba", "Heritage Bank Stadium"},  # QLD
        {"Blundstone Arena", "University of Tasmania Stadium"},  # TAS
    ]
    for group in city_groups:
        if venue1 in group and venue2 in group:
            return False
    return True

# Build per-team travel log and fatigue scores
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
                match['fatigue_score'] = None
                match['notes'] = f"Unknown venue: {venue}"
                travel_log.append({**match, 'team': team})
                continue

            distance = 0
            short_rest = False
            timezone_change = False
            this_week_real_travel = False

            if last_venue:
                prev_coords = STADIUM_COORDS.get(last_venue)
                if prev_coords and is_real_travel(last_venue, venue):
                    this_week_real_travel = True
                    distance = haversine(prev_coords, latlon)
                    timezone_change = abs(
                        timezone_offset(prev_coords[0]) - timezone_offset(latlon[0])
                    ) >= 2

                if last_time:
                    days_rest = (dt - last_time).days
                    short_rest = days_rest < 6

            # Final back-to-back logic
            back_to_back_travel = last_week_real_travel and this_week_real_travel

            # Fatigue score logic
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

            # Update for next loop
            last_venue = venue
            last_time = dt
            last_week_real_travel = this_week_real_travel

            travel_log.append(match)

    return travel_log

# Preview in console
if __name__ == "__main__":
    log = build_travel_log()
    print(f"\n{'Team':<15} {'Round':<5} {'Opponent':<15} {'Venue':<25} {'Fatigue':<7} {'Notes'}")
    print("-" * 90)
    for entry in log:
        if entry.get('fatigue_score') is not None:
            print(f"{entry['team']:<15} {entry['round']:<5} {entry['opponent']:<15} {entry['venue']:<25} {entry['fatigue_score']:<7} {entry['notes']}")

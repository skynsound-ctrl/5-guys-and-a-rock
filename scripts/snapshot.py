"""Daily snapshot: pull league state from Sleeper and save it as JSON in data/.

Run by .github/workflows/snapshot.yml once a day. No AI, no computed stats —
just a faithful copy of what Sleeper returned, so later steps (facts.py) have
something stable to read and diff against.
"""
import json
import pathlib
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
API = "https://api.sleeper.app/v1"

# Fields we actually use from the ~5MB /players/nfl response. Keeping this
# narrow is what makes the filtered file small enough to commit to git.
PLAYER_FIELDS = (
    "full_name",
    "team",
    "position",
    "injury_status",
    "injury_body_part",
    "practice_participation",
    "news_updated",
)


def get(path):
    r = requests.get(API + path, timeout=30)
    r.raise_for_status()
    return r.json()


def write_json(relative_path, data):
    path = DATA / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"wrote {relative_path}")


def main():
    config = json.loads((ROOT / "scripts" / "config.json").read_text())
    league_id = config["league_id"]

    state = get("/state/nfl")
    week = state.get("display_week") or state.get("week") or 1
    write_json("state.json", state)

    write_json("league.json", get(f"/league/{league_id}"))
    write_json("users.json", get(f"/league/{league_id}/users"))
    write_json("rosters.json", get(f"/league/{league_id}/rosters"))

    try:
        matchups = get(f"/league/{league_id}/matchups/{week}")
    except requests.HTTPError:
        matchups = []
    write_json(f"matchups/week-{week:02d}.json", matchups)
    if not matchups:
        print(f"no matchups published yet for week {week} — that's normal in the preseason")

    players = get("/players/nfl?active=true")
    filtered = {
        pid: {field: p.get(field) for field in PLAYER_FIELDS}
        for pid, p in players.items()
    }
    write_json("players.json", filtered)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"Sleeper request failed: {e}", file=sys.stderr)
        sys.exit(1)

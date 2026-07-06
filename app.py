from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta, timezone
from itertools import combinations
import os
import math

app = Flask(__name__)

KST = timezone(timedelta(hours=9))
ODDS_API_KEY = os.getenv("ODDS_API_KEY")


# =========================
# Demo Data
# =========================

def demo_games(sport="all"):
    now = datetime.now(KST)

    games = [
        {
            "sport": "baseball",
            "league": "KBO",
            "home": "LG",
            "away": "두산",
            "starts_at": (now + timedelta(minutes=42)).isoformat(),
            "markets": [
                {
                    "pick": "LG 승",
                    "type": "ML",
                    "odds": 1.70,
                    "open_odds": 1.82,
                    "sharp_odds": 1.68,
                    "domestic_odds": 1.74,
                    "bookmaker": "Pinnacle",
                },
                {
                    "pick": "두산 승",
                    "type": "ML",
                    "odds": 2.12,
                    "open_odds": 2.02,
                    "sharp_odds": 2.18,
                    "domestic_odds": 2.05,
                    "bookmaker": "Pinnacle",
                },
            ],
        },
        {
            "sport": "soccer",
            "league": "EPL",
            "home": "Arsenal",
            "away": "Chelsea",
            "starts_at": (now + timedelta(minutes=47)).isoformat(),
            "markets": [
                {
                    "pick": "Arsenal 승",
                    "type": "1X2",
                    "odds": 1.78,
                    "open_odds": 1.91,
                    "sharp_odds": 1.74,
                    "domestic_odds": 1.84,
                    "bookmaker": "Pinnacle",
                },
                {
                    "pick": "무승부",
                    "type": "1X2",
                    "odds": 3.45,
                    "open_odds": 3.30,
                    "sharp_odds": 3.38,
                    "domestic_odds": 3.50,
                    "bookmaker": "Bet365",
                },
                {
                    "pick": "Chelsea 승",
                    "type": "1X2",
                    "odds": 4.20,
                    "open_odds": 4.00,
                    "sharp_odds": 4.30,
                    "domestic_odds": 4.10,
                    "bookmaker": "Bet365",
                },
            ],
        },
        {
            "sport": "soccer",
            "league": "LaLiga",
            "home": "Valencia",
            "away": "Sevilla",
            "starts_at": (now + timedelta(minutes=58)).isoformat(),
            "markets": [
                {
                    "pick": "Sevilla +0.5",
                    "type": "Handicap",
                    "odds": 1.82,
                    "open_odds": 1.95,
                    "sharp_odds": 1.77,
                    "domestic_odds": 1.86,
                    "bookmaker": "Pinnacle",
                },
                {
                    "pick": "Valencia 승",
                    "type": "ML",
                    "odds": 2.05,
                    "open_odds": 1.91,
                    "sharp_odds": 2.12,
                    "domestic_odds": 2.02,
                    "bookmaker": "Bet365",
                },
            ],
        },
        {
            "sport": "baseball",
            "league": "MLB",
            "home": "Dodgers",
            "away": "Padres",
            "starts_at": (now + timedelta(minutes=35)).isoformat(),
            "markets": [
                {
                    "pick": "Dodgers 승",
                    "type": "ML",
                    "odds": 1.79,
                    "open_odds": 2.05,
                    "sharp_odds": 1.71,
                    "domestic_odds": 1.88,
                    "bookmaker": "Pinnacle",
                },
                {
                    "pick": "Padres +1.5",
                    "type": "Handicap",
                    "odds": 1.91,
                    "open_odds": 1.87,
                    "sharp_odds": 1.94,
                    "domestic_odds": 1.90,
                    "bookmaker": "Bet365",
                },
            ],
        },
    ]

    if sport != "all":
        games = [g for g in games if g["sport"] == sport]

    return games


# =========================
# Calculation Engine
# =========================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def start_in_minutes(starts_at):
    try:
        start = datetime.fromisoformat(starts_at)
        now = datetime.now(KST)
        return int((start - now).total_seconds() // 60)
    except Exception:
        return None


def drop_rate(open_odds, current_odds):
    open_odds = safe_float(open_odds)
    current_odds = safe_float(current_odds)

    if open_odds <= 0 or current_odds <= 0:
        return 0

    return round(((open_odds - current_odds) / open_odds) * 100, 2)


def implied_probability(odds):
    odds = safe_float(odds)

    if odds <= 0:
        return 0

    return round((1 / odds) * 100, 2)


def ev_percent(score, odds):
    odds = safe_float(odds)
    score = safe_float(score)

    if odds <= 0 or score <= 0:
        return 0

    probability = score / 100
    return round((probability * odds - 1) * 100, 2)


def kelly_percent(score, odds):
    odds = safe_float(odds)
    score = safe_float(score)

    if odds <= 1 or score <= 0:
        return 0

    p = score / 100
    b = odds - 1
    kelly = ((b * p) - (1 - p)) / b

    return round(max(0, kelly * 100), 2)


def sharp_component(open_odds, current_odds, sharp_odds):
    d = drop_rate(open_odds, current_odds)

    sharp_gap = 0
    if sharp_odds and current_odds:
        sharp_gap = (safe_float(current_odds) - safe_float(sharp_odds)) / safe_float(current_odds) * 100

    score = 0

    if d >= 8:
        score += 35
    elif d >= 5:
        score += 28
    elif d >= 3:
        score += 20
    elif d >= 1:
        score += 10

    if sharp_gap >= 3:
        score += 25
    elif sharp_gap >= 1.5:
        score += 15
    elif sharp_gap >= 0.5:
        score += 8

    return min(40, round(score, 1))


def steam_component(open_odds, current_odds):
    d = drop_rate(open_odds, current_odds)

    if d >= 10:
        return 25
    if d >= 7:
        return 21
    if d >= 5:
        return 16
    if d >= 3:
        return 10
    if d >= 1:
        return 5

    return 0


def clv_component(current_odds, sharp_odds, domestic_odds):
    current_odds = safe_float(current_odds)
    sharp_odds = safe_float(sharp_odds)
    domestic_odds = safe_float(domestic_odds)

    score = 0

    if sharp_odds and current_odds:
        if sharp_odds < current_odds:
            score += 12

    if domestic_odds and sharp_odds:
        if domestic_odds > sharp_odds:
            score += 12

    return min(20, score)


def value_component(score, odds):
    ev = ev_percent(score, odds)

    if ev >= 20:
        return 15
    if ev >= 10:
        return 10
    if ev >= 5:
        return 6
    if ev > 0:
        return 3

    return 0


def risk_level(score, d, ev):
    if score >= 85 and d >= 4 and ev > 0:
        return "low"
    if score >= 72 and ev > 0:
        return "medium"
    return "high"


def reasons_for_pick(market, score, d, ev):
    reasons = []

    if d >= 5:
        reasons.append("초기 대비 강한 하락")
    elif d >= 2:
        reasons.append("배당 하락")

    if market.get("sharp_odds") and safe_float(market["sharp_odds"]) < safe_float(market["odds"]):
        reasons.append("피나클 하락")

    if market.get("domestic_odds") and market.get("sharp_odds"):
        if safe_float(market["domestic_odds"]) > safe_float(market["sharp_odds"]):
            reasons.append("국내 배당 유지")

    if ev > 10:
        reasons.append("EV 우수")
    elif ev > 0:
        reasons.append("EV 양호")

    if score >= 85:
        reasons.append("AI 고점수")

    return reasons or ["관찰 필요"]


def analyze_market(game, market):
    open_odds = safe_float(market.get("open_odds"))
    odds = safe_float(market.get("odds"))
    sharp_odds = safe_float(market.get("sharp_odds"))
    domestic_odds = safe_float(market.get("domestic_odds"))

    d = drop_rate(open_odds, odds)

    base_score = 45
    sharp = sharp_component(open_odds, odds, sharp_odds)
    steam = steam_component(open_odds, odds)
    clv = clv_component(odds, sharp_odds, domestic_odds)

    temporary_score = min(99, base_score + sharp + steam + clv)
    value = value_component(temporary_score, odds)

    score = min(99, round(base_score + sharp + steam + clv + value))
    ev = ev_percent(score, odds)
    kelly = kelly_percent(score, odds)

    risk = risk_level(score, d, ev)

    return {
        "sport": game.get("sport"),
        "league": game.get("league"),
        "game": f"{game.get('league')} {game.get('home')} vs {game.get('away')}",
        "home": game.get("home"),
        "away": game.get("away"),
        "starts_at": game.get("starts_at"),
        "start_in_minutes": start_in_minutes(game.get("starts_at")),
        "type": market.get("type"),
        "pick": market.get("pick"),
        "bookmaker": market.get("bookmaker"),
        "odds": odds,
        "open_odds": open_odds,
        "sharp_odds": sharp_odds,
        "domestic_odds": domestic_odds,
        "drop_rate": d,
        "implied_probability": implied_probability(odds),
        "score": score,
        "ev": ev,
        "kelly": kelly,
        "sharp_score": sharp,
        "steam_score": steam,
        "clv_score": clv,
        "value_score": value,
        "risk": risk,
        "reasons": reasons_for_pick(market, score, d, ev),
    }


def flatten_picks(games):
    picks = []

    for game in games:
        for market in game.get("markets", []):
            picks.append(analyze_market(game, market))

    return sorted(picks, key=lambda x: (x["score"], x["ev"], x["drop_rate"]), reverse=True)


def make_combo(name, picks, size=2):
    picks = picks[:8]
    best = None

    for combo in combinations(picks, size):
        total_odds = math.prod([safe_float(p["odds"], 1) for p in combo])
        avg_score = sum([p["score"] for p in combo]) / len(combo)
        avg_ev = sum([p["ev"] for p in combo]) / len(combo)
        avg_kelly = sum([p["kelly"] for p in combo]) / len(combo)

        item = {
            "type": name,
            "total_odds": round(total_odds, 2),
            "avg_score": round(avg_score, 1),
            "avg_ev": round(avg_ev, 2),
            "avg_kelly": round(avg_kelly, 2),
            "picks": list(combo),
        }

        if best is None:
            best = item
        elif (item["avg_score"], item["avg_ev"]) > (best["avg_score"], best["avg_ev"]):
            best = item

    return best


def build_recommendations(games):
    picks = flatten_picks(games)

    safe = [p for p in picks if p["score"] >= 80 and p["risk"] == "low"]
    balanced = [p for p in picks if p["score"] >= 70 and p["risk"] in ["low", "medium"]]
    aggressive = [p for p in picks if p["score"] >= 60]

    combos = []

    if len(safe) >= 2:
        combos.append(make_combo("신중형", safe, 2))

    if len(balanced) >= 2:
        combos.append(make_combo("균형형", balanced, 2))

    if len(aggressive) >= 2:
        combos.append(make_combo("공격형", aggressive, 2))

    combos = [c for c in combos if c]

    return combos, picks


# =========================
# Routes
# =========================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/live-games")
def live_games():
    sport = request.args.get("sport", "all")
    minutes = int(request.args.get("minutes", 60))

    games = demo_games(sport)

    return jsonify({
        "mode": "demo",
        "sport": sport,
        "minutes": minutes,
        "count": len(games),
        "games": games,
        "notice": "현재는 데모 데이터입니다. V9에서 실시간 Odds API를 연결합니다."
    })


@app.route("/api/recommendations")
def recommendations():
    sport = request.args.get("sport", "all")
    minutes = int(request.args.get("minutes", 60))

    games = demo_games(sport)
    combos, picks = build_recommendations(games)

    excluded = [
        {
            "game": p["game"],
            "pick": p["pick"],
            "score": p["score"],
            "risk": p["risk"],
            "reason": "점수 부족 또는 위험도 높음"
        }
        for p in picks
        if p["score"] < 60 or p["risk"] == "high"
    ]

    return jsonify({
        "mode": "demo",
        "sport": sport,
        "minutes": minutes,
        "combos": combos,
        "top_picks": picks[:10],
        "excluded": excluded,
        "notice": "V8 AI 엔진 적용 완료: EV, Kelly, Sharp, Steam, CLV 계산 포함"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

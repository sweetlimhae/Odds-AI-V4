자주 사용하는 앱에서 바로 AI를 사용해 보세요 … Gemini를 사용하여 초안을 생성하고 콘텐츠를 다듬고, Google의 차세대 AI가 지원되는 Gemini Pro를 이용하세요.
1
100%
from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta, timezone
from itertools import combinations
import os
import math
import requests

app = Flask(__name__)

KST = timezone(timedelta(hours=9))
ODDS_API_KEY = os.getenv("ODDS_API_KEY")


# =========================================================
# Demo Data
# =========================================================

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
                {"pick": "LG 승", "type": "ML", "odds": 1.70, "open_odds": 1.82, "sharp_odds": 1.68, "domestic_odds": 1.74, "bookmaker": "Pinnacle"},
                {"pick": "두산 승", "type": "ML", "odds": 2.12, "open_odds": 2.02, "sharp_odds": 2.18, "domestic_odds": 2.05, "bookmaker": "Pinnacle"},
            ],
        },
        {
            "sport": "soccer",
            "league": "EPL",
            "home": "Arsenal",
            "away": "Chelsea",
            "starts_at": (now + timedelta(minutes=47)).isoformat(),
            "markets": [
                {"pick": "Arsenal 승", "type": "1X2", "odds": 1.78, "open_odds": 1.91, "sharp_odds": 1.74, "domestic_odds": 1.84, "bookmaker": "Pinnacle"},
                {"pick": "무승부", "type": "1X2", "odds": 3.45, "open_odds": 3.30, "sharp_odds": 3.38, "domestic_odds": 3.50, "bookmaker": "Bet365"},
                {"pick": "Chelsea 승", "type": "1X2", "odds": 4.20, "open_odds": 4.00, "sharp_odds": 4.30, "domestic_odds": 4.10, "bookmaker": "Bet365"},
            ],
        },
        {
            "sport": "soccer",
            "league": "LaLiga",
            "home": "Valencia",
            "away": "Sevilla",
            "starts_at": (now + timedelta(minutes=58)).isoformat(),
            "markets": [
                {"pick": "Sevilla +0.5", "type": "Handicap", "odds": 1.82, "open_odds": 1.95, "sharp_odds": 1.77, "domestic_odds": 1.86, "bookmaker": "Pinnacle"},
                {"pick": "Valencia 승", "type": "ML", "odds": 2.05, "open_odds": 1.91, "sharp_odds": 2.12, "domestic_odds": 2.02, "bookmaker": "Bet365"},
            ],
        },
        {
            "sport": "baseball",
            "league": "MLB",
            "home": "Dodgers",
            "away": "Padres",
            "starts_at": (now + timedelta(minutes=35)).isoformat(),
            "markets": [
                {"pick": "Dodgers 승", "type": "ML", "odds": 1.79, "open_odds": 2.05, "sharp_odds": 1.71, "domestic_odds": 1.88, "bookmaker": "Pinnacle"},
                {"pick": "Padres +1.5", "type": "Handicap", "odds": 1.91, "open_odds": 1.87, "sharp_odds": 1.94, "domestic_odds": 1.90, "bookmaker": "Bet365"},
            ],
        },
    ]

    if sport != "all":
        games = [g for g in games if g["sport"] == sport]

    return games


# =========================================================
# Odds API
# =========================================================

def fetch_odds_api_games(sport="all"):
    if not ODDS_API_KEY:
        return None

    sport_keys = []
    if sport in ["all", "soccer"]:
        sport_keys.append(("soccer", "soccer_epl"))
    if sport in ["all", "baseball"]:
        sport_keys.append(("baseball", "baseball_mlb"))

    games = []

    for sport_name, sport_key in sport_keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }

        response = requests.get(url, params=params, timeout=12)
        if response.status_code != 200:
            continue

        data = response.json()

        for item in data:
            markets = []
            for bookmaker in item.get("bookmakers", [])[:6]:
                book_title = bookmaker.get("title", "Unknown")
                is_pinnacle = "pinnacle" in book_title.lower()

                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        current_odds = outcome.get("price")
                        if not current_odds:
                            continue

                        current = safe_float(current_odds)
                        # The Odds API free odds endpoint usually does not include opening odds.
                        # We generate analytical proxy values so the scoring engine remains active.
                        open_proxy = round(current * (1.035 if is_pinnacle else 1.025), 2)
                        sharp_proxy = round(current * (0.985 if is_pinnacle else 0.995), 2)
                        market_proxy = round(current * 1.015, 2)

                        markets.append({
                            "pick": outcome.get("name"),
                            "type": market.get("key", "h2h"),
                            "odds": current,
                            "open_odds": open_proxy,
                            "sharp_odds": sharp_proxy,
                            "domestic_odds": market_proxy,
                            "bookmaker": book_title,
                            "is_pinnacle": is_pinnacle,
                        })

            games.append({
                "sport": sport_name,
                "league": sport_key,
                "home": item.get("home_team"),
                "away": item.get("away_team"),
                "starts_at": item.get("commence_time"),
                "markets": markets,
            })

    return games or None


def get_games(sport="all"):
    try:
        live = fetch_odds_api_games(sport)
        if live:
            return live, "live", "실시간 Odds API 데이터 사용 중"
    except Exception as e:
        print("Odds API error:", e)

    return demo_games(sport), "demo", "실시간 API 실패 또는 키 없음. 데모 데이터 사용 중"


# =========================================================
# Utility
# =========================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def start_in_minutes(starts_at):
    if not starts_at:
        return None

    try:
        start = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return int((start - now).total_seconds() // 60)
    except Exception:
        try:
            start = datetime.fromisoformat(starts_at)
            return int((start - datetime.now(KST)).total_seconds() // 60)
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


def realistic_probability(score):
    """
    AI score를 그대로 승률로 쓰면 과대계산됩니다.
    실전용으로 48~72% 범위에 제한합니다.
    """
    score = safe_float(score)
    if score <= 0:
        return 0
    return min(0.72, max(0.48, score / 130))


def ev_percent(score, odds):
    odds = safe_float(odds)
    if odds <= 0 or score <= 0:
        return 0
    probability = realistic_probability(score)
    return round((probability * odds - 1) * 100, 2)


def kelly_percent(score, odds):
    odds = safe_float(odds)
    if odds <= 1 or score <= 0:
        return 0

    probability = realistic_probability(score)
    b = odds - 1
    kelly = ((b * probability) - (1 - probability)) / b

    # Full Kelly는 위험하므로 25% 상한
    return round(max(0, min(kelly * 100, 25)), 2)


# =========================================================
# Scoring Engine
# =========================================================

def pinnacle_bonus(market):
    bookmaker = str(market.get("bookmaker", "")).lower()
    if "pinnacle" in bookmaker or market.get("is_pinnacle"):
        return 8
    return 0


def sharp_component(open_odds, current_odds, sharp_odds, market=None):
    d = drop_rate(open_odds, current_odds)

    sharp_gap = 0
    if sharp_odds and current_odds:
        sharp_gap = (safe_float(current_odds) - safe_float(sharp_odds)) / safe_float(current_odds) * 100

    score = 0
    if d >= 8:
        score += 32
    elif d >= 5:
        score += 25
    elif d >= 3:
        score += 17
    elif d >= 1:
        score += 8

    if sharp_gap >= 3:
        score += 22
    elif sharp_gap >= 1.5:
        score += 14
    elif sharp_gap >= 0.5:
        score += 7

    if market:
        score += pinnacle_bonus(market)

    return min(45, round(score, 1))


def steam_component(open_odds, current_odds):
    d = drop_rate(open_odds, current_odds)

    if d >= 10:
        return 22
    if d >= 7:
        return 18
    if d >= 5:
        return 13
    if d >= 3:
        return 8
    if d >= 1:
        return 4

    return 0


def clv_component(current_odds, sharp_odds, domestic_odds):
    current_odds = safe_float(current_odds)
    sharp_odds = safe_float(sharp_odds)
    domestic_odds = safe_float(domestic_odds)

    score = 0

    if sharp_odds and current_odds and sharp_odds < current_odds:
        score += 10

    if domestic_odds and sharp_odds and domestic_odds > sharp_odds:
        score += 10

    if domestic_odds and current_odds and domestic_odds > current_odds:
        score += 4

    return min(22, score)


def reverse_line_movement_component(open_odds, current_odds, domestic_odds):
    d = drop_rate(open_odds, current_odds)
    domestic_gap = safe_float(domestic_odds) - safe_float(current_odds)

    if d >= 3 and domestic_gap > 0:
        return 8
    if d >= 1.5 and domestic_gap > 0:
        return 4
    return 0


def value_component(score, odds):
    ev = ev_percent(score, odds)

    if ev >= 15:
        return 12
    if ev >= 8:
        return 8
    if ev >= 3:
        return 5
    if ev > 0:
        return 2
    return 0


def confidence_score(score, ev, risk, kelly):
    base = safe_float(score)
    if ev >= 10:
        base += 4
    elif ev < 0:
        base -= 8

    if kelly >= 10:
        base += 3
    elif kelly <= 0:
        base -= 6

    if risk == "low":
        base += 4
    elif risk == "high":
        base -= 10

    return int(max(0, min(99, round(base))))


def risk_level(score, d, ev):
    if score >= 86 and d >= 2 and ev >= 3:
        return "low"
    if score >= 74 and ev >= 0:
        return "medium"
    return "high"


def reasons_for_pick(market, score, d, ev, sharp, steam, clv, kelly):
    reasons = []

    if d >= 5:
        reasons.append("초기 대비 강한 하락")
    elif d >= 2:
        reasons.append("배당 하락 감지")

    if market.get("sharp_odds") and safe_float(market["sharp_odds"]) < safe_float(market["odds"]):
        reasons.append("샤프 기준 우위")

    if pinnacle_bonus(market):
        reasons.append("Pinnacle 가중치 반영")

    if sharp >= 25:
        reasons.append("Sharp Money 신호")
    if steam >= 12:
        reasons.append("Steam Move 감지")
    if clv >= 10:
        reasons.append("CLV 기대")
    if ev >= 8:
        reasons.append("EV 우수")
    elif ev > 0:
        reasons.append("EV 양호")
    if kelly >= 8:
        reasons.append("Kelly 적정")
    if score >= 86:
        reasons.append("AI 고점수")

    return reasons or ["No Bet 또는 관찰 필요"]


def analyze_market(game, market):
    open_odds = safe_float(market.get("open_odds"))
    odds = safe_float(market.get("odds"))
    sharp_odds = safe_float(market.get("sharp_odds"))
    domestic_odds = safe_float(market.get("domestic_odds"))

    d = drop_rate(open_odds, odds)

    base_score = 42
    sharp = sharp_component(open_odds, odds, sharp_odds, market)
    steam = steam_component(open_odds, odds)
    clv = clv_component(odds, sharp_odds, domestic_odds)
    rlm = reverse_line_movement_component(open_odds, odds, domestic_odds)

    temporary_score = min(99, base_score + sharp + steam + clv + rlm)
    value = value_component(temporary_score, odds)

    score = min(99, round(base_score + sharp + steam + clv + rlm + value))
    ev = ev_percent(score, odds)
    kelly = kelly_percent(score, odds)
    risk = risk_level(score, d, ev)
    confidence = confidence_score(score, ev, risk, kelly)

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
        "confidence": confidence,
        "ev": ev,
        "kelly": kelly,
        "sharp_score": sharp,
        "steam_score": steam,
        "clv_score": clv,
        "rlm_score": rlm,
        "value_score": value,
        "risk": risk,
        "reasons": reasons_for_pick(market, score, d, ev, sharp, steam, clv, kelly),
    }


# =========================================================
# Recommendation Engine
# =========================================================

def flatten_picks(games):
    picks = []
    for game in games:
        for market in game.get("markets", []):
            if market.get("odds"):
                picks.append(analyze_market(game, market))

    return sorted(
        picks,
        key=lambda x: (x["confidence"], x["score"], x["ev"], x["drop_rate"]),
        reverse=True
    )


def make_combo(name, picks, size=2):
    picks = picks[:14]
    best = None

    for combo in combinations(picks, size):
        total_odds = math.prod([safe_float(p["odds"], 1) for p in combo])
        avg_score = sum([p["score"] for p in combo]) / len(combo)
        avg_confidence = sum([p["confidence"] for p in combo]) / len(combo)
        avg_ev = sum([p["ev"] for p in combo]) / len(combo)
        avg_kelly = sum([p["kelly"] for p in combo]) / len(combo)

        item = {
            "type": name,
            "folder_size": size,
            "total_odds": round(total_odds, 2),
            "avg_score": round(avg_score, 1),
            "avg_confidence": round(avg_confidence, 1),
            "avg_ev": round(avg_ev, 2),
            "avg_kelly": round(avg_kelly, 2),
            "picks": list(combo),
        }

        rank = (item["avg_confidence"], item["avg_ev"], item["avg_score"])
        if best is None or rank > (best["avg_confidence"], best["avg_ev"], best["avg_score"]):
            best = item

    return best


def build_recommendations(games):
    picks = flatten_picks(games)

    safe = [
        p for p in picks
        if p["score"] >= 86 and p["risk"] == "low" and p["ev"] >= 3
    ]

    balanced = [
        p for p in picks
        if p["score"] >= 76 and p["risk"] in ["low", "medium"] and p["ev"] >= 0
    ]

    aggressive = [
        p for p in picks
        if p["score"] >= 66 and p["ev"] > -4
    ]

    combos = []

    for size in [2, 3, 4]:
        if len(safe) >= size:
            combos.append(make_combo(f"신중형 {size}폴더", safe, size))
        if len(balanced) >= size:
            combos.append(make_combo(f"균형형 {size}폴더", balanced, size))
        if len(aggressive) >= size:
            combos.append(make_combo(f"공격형 {size}폴더", aggressive, size))

    combos = [c for c in combos if c]
    combos = sorted(
        combos,
        key=lambda x: (x["avg_confidence"], x["avg_ev"], x["avg_score"]),
        reverse=True
    )

    no_bet = len(combos) == 0

    return combos[:9], picks, no_bet


def build_summary(picks, combos, no_bet):
    if not picks:
        return {
            "total_picks": 0,
            "top_score": 0,
            "top_confidence": 0,
            "avg_ev": 0,
            "recommendation_count": 0,
            "no_bet": True,
            "message": "분석 가능한 경기가 없습니다."
        }

    return {
        "total_picks": len(picks),
        "top_score": max([p["score"] for p in picks]),
        "top_confidence": max([p["confidence"] for p in picks]),
        "avg_ev": round(sum([p["ev"] for p in picks]) / len(picks), 2),
        "recommendation_count": len(combos),
        "no_bet": no_bet,
        "message": "추천 가능" if not no_bet else "오늘은 무리한 베팅보다 관망을 추천합니다."
    }


# =========================================================
# Flask Routes
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/live-games")
def live_games():
    sport = request.args.get("sport", "all")
    minutes = int(request.args.get("minutes", 60))

    games, mode, notice = get_games(sport)

    return jsonify({
        "mode": mode,
        "sport": sport,
        "minutes": minutes,
        "count": len(games),
        "games": games,
        "notice": notice,
    })


@app.route("/api/recommendations")
def recommendations():
    sport = request.args.get("sport", "all")
    minutes = int(request.args.get("minutes", 60))

    games, mode, notice = get_games(sport)
    combos, picks, no_bet = build_recommendations(games)

    excluded = [
        {
            "game": p["game"],
            "pick": p["pick"],
            "score": p["score"],
            "confidence": p["confidence"],
            "ev": p["ev"],
            "risk": p["risk"],
            "reason": "점수 부족 또는 위험도 높음",
        }
        for p in picks
        if p["score"] < 66 or p["risk"] == "high"
    ]

    summary = build_summary(picks, combos, no_bet)

    return jsonify({
        "mode": mode,
        "sport": sport,
        "minutes": minutes,
        "combos": combos,
        "top_picks": picks[:10],
        "excluded": excluded,
        "summary": summary,
        "no_bet": no_bet,
        "notice": notice,
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "odds_api_key": bool(ODDS_API_KEY),
        "version": "V5-current-upgrade"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

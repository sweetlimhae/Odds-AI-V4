from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta, timezone
from itertools import combinations
import os
import math
import requests

app = Flask(__name__)

KST = timezone(timedelta(hours=9))
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
MIN_START_MINUTES = int(os.getenv("MIN_START_MINUTES", "10"))
MAX_START_MINUTES = int(os.getenv("MAX_START_MINUTES", "120"))


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def now_kst():
    return datetime.now(KST)


def start_in_minutes(starts_at):
    if not starts_at:
        return None
    try:
        start = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return int((start - now).total_seconds() // 60)
    except Exception:
        try:
            start = datetime.fromisoformat(str(starts_at))
            return int((start - now_kst()).total_seconds() // 60)
        except Exception:
            return None


def valid_start_time(starts_at):
    mins = start_in_minutes(starts_at)
    return mins is not None and MIN_START_MINUTES <= mins <= MAX_START_MINUTES


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


def market_average(values):
    nums = [safe_float(v) for v in values if safe_float(v) > 1]
    if not nums:
        return 0
    return round(sum(nums) / len(nums), 3)


def realistic_probability(score):
    score = safe_float(score)
    if score <= 0:
        return 0
    return min(0.72, max(0.45, score / 135))


def ev_percent(score, odds):
    odds = safe_float(odds)
    if odds <= 1 or score <= 0:
        return 0
    p = realistic_probability(score)
    return round((p * odds - 1) * 100, 2)


def kelly_percent(score, odds):
    odds = safe_float(odds)
    if odds <= 1 or score <= 0:
        return 0
    p = realistic_probability(score)
    b = odds - 1
    k = ((b * p) - (1 - p)) / b
    return round(max(0, min(k * 100, 15)), 2)


def demo_games(sport="all"):
    now = now_kst()
    games = [
        {
            "sport": "baseball", "league": "KBO", "home": "LG", "away": "두산",
            "starts_at": (now + timedelta(minutes=42)).isoformat(),
            "markets": [
                {"pick": "LG 승", "type": "ML", "odds": 1.70, "open_odds": 1.82, "pinnacle_odds": 1.68, "market_avg": 1.76, "bookmaker": "Pinnacle", "is_pinnacle": True},
                {"pick": "두산 승", "type": "ML", "odds": 2.12, "open_odds": 2.02, "pinnacle_odds": 2.12, "market_avg": 2.08, "bookmaker": "Pinnacle", "is_pinnacle": True},
            ],
        },
        {
            "sport": "soccer", "league": "EPL", "home": "Arsenal", "away": "Chelsea",
            "starts_at": (now + timedelta(minutes=47)).isoformat(),
            "markets": [
                {"pick": "Arsenal", "type": "1X2", "odds": 1.78, "open_odds": 1.91, "pinnacle_odds": 1.74, "market_avg": 1.84, "bookmaker": "Pinnacle", "is_pinnacle": True},
                {"pick": "Draw", "type": "1X2", "odds": 3.45, "open_odds": 3.30, "pinnacle_odds": 3.42, "market_avg": 3.50, "bookmaker": "Bet365", "is_pinnacle": False},
                {"pick": "Chelsea", "type": "1X2", "odds": 4.20, "open_odds": 4.00, "pinnacle_odds": 4.18, "market_avg": 4.10, "bookmaker": "Bet365", "is_pinnacle": False},
            ],
        },
        {
            "sport": "soccer", "league": "LaLiga", "home": "Valencia", "away": "Sevilla",
            "starts_at": (now + timedelta(minutes=58)).isoformat(),
            "markets": [
                {"pick": "Sevilla +0.5", "type": "Handicap", "odds": 1.82, "open_odds": 1.95, "pinnacle_odds": 1.77, "market_avg": 1.88, "bookmaker": "Pinnacle", "is_pinnacle": True},
                {"pick": "Valencia", "type": "ML", "odds": 2.05, "open_odds": 1.91, "pinnacle_odds": 2.04, "market_avg": 2.02, "bookmaker": "Bet365", "is_pinnacle": False},
            ],
        },
    ]
    if sport != "all":
        games = [g for g in games if g["sport"] == sport]
    return [g for g in games if valid_start_time(g.get("starts_at"))]


def supported_sports(sport):
    keys = []
    if sport in ["all", "soccer"]:
        keys.extend([
            ("soccer", "soccer_epl"),
            ("soccer", "soccer_spain_la_liga"),
            ("soccer", "soccer_italy_serie_a"),
            ("soccer", "soccer_germany_bundesliga"),
        ])
    if sport in ["all", "baseball"]:
        keys.append(("baseball", "baseball_mlb"))
    return keys


def fetch_odds_api_games(sport="all"):
    if not ODDS_API_KEY:
        return None
    games = []
    for sport_name, sport_key in supported_sports(sport):
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        params = {"apiKey": ODDS_API_KEY, "regions": "us,eu,uk", "markets": "h2h", "oddsFormat": "decimal"}
        try:
            response = requests.get(url, params=params, timeout=12)
        except Exception:
            continue
        if response.status_code != 200:
            continue
        for item in response.json():
            starts_at = item.get("commence_time")
            if not valid_start_time(starts_at):
                continue
            outcome_map = {}
            for bookmaker in item.get("bookmakers", []):
                book_title = bookmaker.get("title", "Unknown")
                is_pinnacle = "pinnacle" in book_title.lower()
                for market in bookmaker.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        pick = outcome.get("name")
                        price = safe_float(outcome.get("price"))
                        if not pick or price <= 1:
                            continue
                        key = pick.lower().strip()
                        if key not in outcome_map:
                            outcome_map[key] = {"pick": pick, "type": "h2h", "all_odds": [], "pinnacle_odds": None, "best_odds": price, "best_bookmaker": book_title, "bookmakers": []}
                        row = outcome_map[key]
                        row["all_odds"].append(price)
                        row["bookmakers"].append({"bookmaker": book_title, "odds": price})
                        if price > row["best_odds"]:
                            row["best_odds"] = price
                            row["best_bookmaker"] = book_title
                        if is_pinnacle:
                            row["pinnacle_odds"] = price
            markets = []
            for row in outcome_map.values():
                avg = market_average(row["all_odds"])
                current = safe_float(row["pinnacle_odds"]) or safe_float(row["best_odds"])
                open_proxy = round(avg * 1.025, 2) if avg else round(current * 1.025, 2)
                markets.append({
                    "pick": row["pick"], "type": row["type"], "odds": current, "open_odds": open_proxy,
                    "pinnacle_odds": row["pinnacle_odds"], "market_avg": avg,
                    "best_odds": row["best_odds"], "bookmaker": "Pinnacle" if row["pinnacle_odds"] else row["best_bookmaker"],
                    "is_pinnacle": bool(row["pinnacle_odds"]), "bookmakers": row["bookmakers"][:12], "source": "odds_api_market_average",
                })
            if markets:
                games.append({"sport": sport_name, "league": sport_key, "home": item.get("home_team"), "away": item.get("away_team"), "starts_at": starts_at, "start_in_minutes": start_in_minutes(starts_at), "markets": markets})
    return games or None


def get_games(sport="all"):
    try:
        live = fetch_odds_api_games(sport)
        if live:
            return live, "live", f"실시간 Odds API 사용 / {MIN_START_MINUTES}~{MAX_START_MINUTES}분 경기만 분석"
    except Exception as e:
        print("Odds API error:", e)
    return demo_games(sport), "demo", "실시간 API 실패 또는 키 없음. 데모 데이터 사용 중"


def pinnacle_bonus(market):
    return 10 if market.get("is_pinnacle") or "pinnacle" in str(market.get("bookmaker", "")).lower() else 0


def value_gap_component(odds, market_avg):
    odds = safe_float(odds)
    market_avg = safe_float(market_avg)
    if odds <= 1 or market_avg <= 1:
        return 0
    gap = ((odds - market_avg) / market_avg) * 100
    if gap >= 5:
        return 18
    if gap >= 3:
        return 13
    if gap >= 1.5:
        return 8
    if gap >= 0.5:
        return 4
    if gap <= -3:
        return -10
    return 0


def sharp_component(open_odds, current_odds, pinnacle_odds, market_avg, market):
    d = drop_rate(open_odds, current_odds)
    score = 0
    if d >= 6:
        score += 25
    elif d >= 4:
        score += 18
    elif d >= 2:
        score += 10
    elif d >= 0.8:
        score += 5
    current = safe_float(current_odds)
    pin = safe_float(pinnacle_odds)
    avg = safe_float(market_avg)
    if pin and avg and pin < avg:
        score += 16
    elif pin and avg and pin <= avg * 1.01:
        score += 8
    if pin and current and abs(pin - current) / current < 0.015:
        score += 6
    score += pinnacle_bonus(market)
    return max(0, min(45, round(score, 1)))


def steam_component(open_odds, current_odds):
    d = drop_rate(open_odds, current_odds)
    if d >= 8:
        return 22
    if d >= 5:
        return 16
    if d >= 3:
        return 10
    if d >= 1:
        return 4
    return 0


def clv_component(current_odds, pinnacle_odds, market_avg):
    current = safe_float(current_odds)
    pin = safe_float(pinnacle_odds)
    avg = safe_float(market_avg)
    score = 0
    if pin and avg and pin < avg:
        score += 12
    if current and avg and current >= avg:
        score += 8
    if pin and current and current >= pin:
        score += 6
    return min(24, score)


def reverse_line_component(open_odds, current_odds, market_avg):
    d = drop_rate(open_odds, current_odds)
    avg = safe_float(market_avg)
    current = safe_float(current_odds)
    if d >= 2 and avg and current <= avg:
        return 8
    if d >= 1 and avg and current <= avg * 1.01:
        return 4
    return 0


def risk_level(score, ev, kelly, d):
    if score >= 86 and ev >= 2 and kelly > 0 and d >= 1:
        return "low"
    if score >= 76 and ev >= -1:
        return "medium"
    return "high"


def confidence_score(score, ev, kelly, risk):
    confidence = safe_float(score)
    if ev >= 8:
        confidence += 5
    elif ev >= 3:
        confidence += 2
    elif ev < -3:
        confidence -= 8
    if kelly >= 5:
        confidence += 3
    elif kelly <= 0:
        confidence -= 4
    if risk == "low":
        confidence += 4
    elif risk == "high":
        confidence -= 10
    return int(max(0, min(99, round(confidence))))


def recommendation_grade(confidence):
    confidence = safe_float(confidence)
    if confidence >= 92:
        return "★★★★★ 강추천"
    if confidence >= 85:
        return "★★★★ 추천"
    if confidence >= 76:
        return "★★★ 관찰"
    return "No Bet"


def reasons_for_pick(market, d, ev, sharp, steam, clv, value_gap, risk, confidence):
    reasons = []
    if market.get("is_pinnacle"):
        reasons.append("Pinnacle 기준 배당 사용")
    if d >= 3:
        reasons.append("초기 대비 배당 하락")
    elif d >= 1:
        reasons.append("배당 하락 감지")
    if sharp >= 25:
        reasons.append("Sharp Money 신호")
    if steam >= 10:
        reasons.append("Steam Move 감지")
    if clv >= 14:
        reasons.append("CLV 기대")
    if value_gap >= 8:
        reasons.append("시장 평균 대비 가치")
    if ev >= 5:
        reasons.append("EV 우수")
    elif ev > 0:
        reasons.append("EV 양호")
    if risk == "low":
        reasons.append("위험도 낮음")
    if confidence >= 85:
        reasons.append("AI 신뢰도 높음")
    return reasons or ["추천 근거 부족"]


def analyze_market(game, market):
    odds = safe_float(market.get("odds"))
    open_odds = safe_float(market.get("open_odds"))
    pinnacle_odds = safe_float(market.get("pinnacle_odds"))
    market_avg = safe_float(market.get("market_avg"))
    d = drop_rate(open_odds, odds)
    base = 38
    sharp = sharp_component(open_odds, odds, pinnacle_odds, market_avg, market)
    steam = steam_component(open_odds, odds)
    clv = clv_component(odds, pinnacle_odds, market_avg)
    value_gap = value_gap_component(odds, market_avg)
    reverse = reverse_line_component(open_odds, odds, market_avg)
    raw_score = base + sharp + steam + clv + value_gap + reverse
    score = int(max(0, min(99, round(raw_score))))
    ev = ev_percent(score, odds)
    kelly = kelly_percent(score, odds)
    risk = risk_level(score, ev, kelly, d)
    confidence = confidence_score(score, ev, kelly, risk)
    return {
        "sport": game.get("sport"), "league": game.get("league"), "game": f"{game.get('league')} {game.get('home')} vs {game.get('away')}",
        "home": game.get("home"), "away": game.get("away"), "starts_at": game.get("starts_at"), "start_in_minutes": game.get("start_in_minutes") or start_in_minutes(game.get("starts_at")),
        "type": market.get("type"), "pick": market.get("pick"), "bookmaker": market.get("bookmaker"),
        "odds": odds, "open_odds": open_odds, "pinnacle_odds": pinnacle_odds, "sharp_odds": pinnacle_odds,
        "market_avg": market_avg, "domestic_odds": market_avg, "best_odds": market.get("best_odds"),
        "drop_rate": d, "implied_probability": implied_probability(odds), "score": score, "confidence": confidence,
        "ev": ev, "kelly": kelly, "sharp_score": sharp, "steam_score": steam, "clv_score": clv,
        "rlm_score": reverse, "value_score": value_gap, "risk": risk, "grade": recommendation_grade(confidence),
        "reasons": reasons_for_pick(market, d, ev, sharp, steam, clv, value_gap, risk, confidence),
        "bookmakers": market.get("bookmakers", []),
    }


def flatten_picks(games):
    picks = []
    for game in games or []:
        if not valid_start_time(game.get("starts_at")):
            continue
        for market in game.get("markets", []):
            if safe_float(market.get("odds")) > 1:
                picks.append(analyze_market(game, market))
    return sorted(picks, key=lambda p: (p["confidence"], p["ev"], p["sharp_score"], p["value_score"]), reverse=True)


def make_combo(name, picks, size):
    candidates = picks[:12]
    best = None
    for combo in combinations(candidates, size):
        game_names = [p["game"] for p in combo]
        if len(set(game_names)) != len(game_names):
            continue
        total_odds = math.prod([safe_float(p["odds"], 1) for p in combo])
        avg_score = sum(p["score"] for p in combo) / size
        avg_confidence = sum(p["confidence"] for p in combo) / size
        avg_ev = sum(p["ev"] for p in combo) / size
        avg_kelly = sum(p["kelly"] for p in combo) / size
        item = {"type": name, "folder_size": size, "total_odds": round(total_odds, 2), "avg_score": round(avg_score, 1), "avg_confidence": round(avg_confidence, 1), "avg_ev": round(avg_ev, 2), "avg_kelly": round(avg_kelly, 2), "picks": list(combo)}
        rank = (item["avg_confidence"], item["avg_ev"], item["avg_score"])
        if best is None or rank > (best["avg_confidence"], best["avg_ev"], best["avg_score"]):
            best = item
    return best


def build_recommendations(games):
    picks = flatten_picks(games)
    strong = [p for p in picks if p["confidence"] >= 86 and p["risk"] == "low" and p["ev"] >= 2]
    normal = [p for p in picks if p["confidence"] >= 78 and p["risk"] in ["low", "medium"] and p["ev"] >= -1]
    watch = [p for p in picks if p["confidence"] >= 70 and p["ev"] >= -4]
    combos = []
    for size in [2, 3, 4]:
        if len(strong) >= size:
            combos.append(make_combo(f"신중형 {size}폴더", strong, size))
        if len(normal) >= size:
            combos.append(make_combo(f"균형형 {size}폴더", normal, size))
        if len(watch) >= size:
            combos.append(make_combo(f"공격형 {size}폴더", watch, size))
    combos = [c for c in combos if c]
    combos = sorted(combos, key=lambda c: (c["avg_confidence"], c["avg_ev"], c["avg_score"]), reverse=True)
    return combos[:9], picks, len(combos) == 0


def build_summary(picks, combos, no_bet):
    if not picks:
        return {"total_picks": 0, "top_score": 0, "top_confidence": 0, "avg_ev": 0, "recommendation_count": 0, "no_bet": True, "message": "10~120분 안에 분석 가능한 경기가 없습니다.", "time_filter": f"{MIN_START_MINUTES}~{MAX_START_MINUTES}분"}
    return {"total_picks": len(picks), "top_score": max(p["score"] for p in picks), "top_confidence": max(p["confidence"] for p in picks), "avg_ev": round(sum(p["ev"] for p in picks) / len(picks), 2), "recommendation_count": len(combos), "no_bet": no_bet, "message": "추천 가능" if not no_bet else "오늘은 무리한 배팅보다 관망을 추천합니다.", "time_filter": f"{MIN_START_MINUTES}~{MAX_START_MINUTES}분"}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/live-games")
def live_games():
    sport = request.args.get("sport", "all")
    minutes = int(request.args.get("minutes", 60))
    games, mode, notice = get_games(sport)
    return jsonify({"mode": mode, "sport": sport, "minutes": minutes, "count": len(games), "games": games, "notice": notice, "time_filter": {"min_minutes": MIN_START_MINUTES, "max_minutes": MAX_START_MINUTES}})


@app.route("/api/recommendations")
def recommendations():
    sport = request.args.get("sport", "all")
    minutes = int(request.args.get("minutes", 60))
    games, mode, notice = get_games(sport)
    combos, picks, no_bet = build_recommendations(games)
    summary = build_summary(picks, combos, no_bet)
    excluded = [{"game": p["game"], "pick": p["pick"], "score": p["score"], "confidence": p["confidence"], "ev": p["ev"], "risk": p["risk"], "reason": "AI 기준 미달 또는 위험도 높음"} for p in picks if p["confidence"] < 70 or p["risk"] == "high"]
    return jsonify({"mode": mode, "sport": sport, "minutes": minutes, "combos": combos, "top_picks": picks[:10], "excluded": excluded, "summary": summary, "no_bet": no_bet, "notice": notice})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "V6-stable-no-playwright", "odds_api_key": bool(ODDS_API_KEY), "time_filter": {"min_minutes": MIN_START_MINUTES, "max_minutes": MAX_START_MINUTES}, "playwright": "disabled_due_to_render_free_memory_limit"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

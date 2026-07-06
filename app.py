from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
KST = timezone(timedelta(hours=9))


def demo_games(sport='soccer'):
    now = datetime.now(KST)
    base = [
        {
            'sport': 'soccer', 'league': 'EPL', 'home': 'Arsenal', 'away': 'Chelsea',
            'starts_at': (now + timedelta(minutes=45)).isoformat(),
            'markets': [
                {'pick': 'Arsenal 승', 'type': '1X2', 'odds': 1.78, 'open_odds': 1.88, 'sharp_odds': 1.74, 'score': 86, 'risk': 'low', 'reasons': ['피나클 하락', '홈승 배당 하락', '시장 평균 대비 괴리']},
                {'pick': '무승부', 'type': '1X2', 'odds': 3.45, 'open_odds': 3.30, 'sharp_odds': 3.55, 'score': 52, 'risk': 'high', 'reasons': ['배당 상승', '샤프 신호 약함']},
            ]
        },
        {
            'sport': 'soccer', 'league': 'LaLiga', 'home': 'Valencia', 'away': 'Sevilla',
            'starts_at': (now + timedelta(minutes=58)).isoformat(),
            'markets': [
                {'pick': '언더 2.5', 'type': 'U/O', 'odds': 1.82, 'open_odds': 1.95, 'sharp_odds': 1.77, 'score': 82, 'risk': 'low', 'reasons': ['언더 동반 하락', '마감 전 하락세']},
                {'pick': 'Sevilla +0.5', 'type': 'Handicap', 'odds': 1.91, 'open_odds': 2.02, 'sharp_odds': 1.87, 'score': 77, 'risk': 'medium', 'reasons': ['핸디캡 하락', '원정 저항 신호']},
            ]
        },
        {
            'sport': 'baseball', 'league': 'KBO', 'home': 'LG', 'away': '두산',
            'starts_at': (now + timedelta(minutes=35)).isoformat(),
            'markets': [
                {'pick': 'LG 승', 'type': 'ML', 'odds': 1.70, 'open_odds': 1.82, 'sharp_odds': 1.68, 'score': 88, 'risk': 'low', 'reasons': ['피나클 하락', '국내 배당 유지', '초기 대비 강한 하락']},
                {'pick': '두산 +1.5', 'type': 'Handicap', 'odds': 1.75, 'open_odds': 1.68, 'sharp_odds': 1.79, 'score': 48, 'risk': 'high', 'reasons': ['반대 신호 충돌']},
            ]
        },
        {
            'sport': 'baseball', 'league': 'MLB', 'home': 'Dodgers', 'away': 'Padres',
            'starts_at': (now + timedelta(minutes=80)).isoformat(),
            'markets': [
                {'pick': '언더 8.5', 'type': 'U/O', 'odds': 1.93, 'open_odds': 2.06, 'sharp_odds': 1.90, 'score': 74, 'risk': 'medium', 'reasons': ['언더 하락', '수익성 양호']},
                {'pick': 'Padres 승', 'type': 'ML', 'odds': 2.35, 'open_odds': 2.55, 'sharp_odds': 2.30, 'score': 68, 'risk': 'high', 'reasons': ['고배당 하락', '공격형 후보']},
            ]
        },
    ]
    return [g for g in base if sport == 'all' or g['sport'] == sport]


def build_combos(games, minutes):
    now = datetime.now(KST)
    cutoff = now + timedelta(minutes=minutes)
    candidates = []
    for g in games:
        start = datetime.fromisoformat(g['starts_at'])
        if now <= start <= cutoff:
            for m in g['markets']:
                candidates.append({**m, 'game': f"{g['league']} {g['home']} vs {g['away']}", 'starts_at': g['starts_at']})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    def combo(kind):
        if kind == 'safe':
            pool = [c for c in candidates if c['score'] >= 80 and c['odds'] <= 1.90]
            title = '신중형'
        elif kind == 'balanced':
            pool = [c for c in candidates if c['score'] >= 72 and 1.70 <= c['odds'] <= 2.10]
            title = '균형형'
        else:
            pool = [c for c in candidates if c['score'] >= 60 and c['odds'] >= 1.85]
            title = '공격형'
        chosen, seen = [], set()
        for c in pool:
            if c['game'] not in seen:
                chosen.append(c); seen.add(c['game'])
            if len(chosen) == 2: break
        total_odds = round(chosen[0]['odds'] * chosen[1]['odds'], 2) if len(chosen)==2 else None
        avg_score = round(sum(c['score'] for c in chosen)/len(chosen), 1) if chosen else None
        return {'type': title, 'total_odds': total_odds, 'avg_score': avg_score, 'picks': chosen}
    return [combo('safe'), combo('balanced'), combo('aggressive')]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/recommendations')
def recommendations():
    sport = request.args.get('sport', 'soccer')
    minutes = int(request.args.get('minutes', '60'))
    games = demo_games(sport)
    return jsonify({'sport': sport, 'minutes': minutes, 'mode': 'demo', 'combos': build_combos(games, minutes)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
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
        "notice": "현재는 데모 데이터입니다. 다음 단계에서 실시간 Odds API를 연결합니다."
    })

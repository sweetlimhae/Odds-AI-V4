const sportEl = document.getElementById("sport");
const minutesEl = document.getElementById("minutes");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");

document.getElementById("gamesBtn").addEventListener("click", loadGames);
document.getElementById("analyzeBtn").addEventListener("click", analyze);

function params() {
  return `sport=${encodeURIComponent(sportEl.value)}&minutes=${encodeURIComponent(minutesEl.value)}`;
}

function setStatus(text) {
  statusEl.innerHTML = text ? `<div class="notice">${text}</div>` : "";
}

function dropRate(openOdds, odds) {
  if (!openOdds || !odds) return "-";
  return (((openOdds - odds) / openOdds) * 100).toFixed(2);
}

function impliedProb(odds) {
  if (!odds) return "-";
  return ((1 / odds) * 100).toFixed(1);
}

function ev(score, odds) {
  if (!score || !odds) return "-";
  return (((score / 100) * odds - 1) * 100).toFixed(2);
}

function kelly(score, odds) {
  if (!score || !odds) return "-";
  const p = score / 100;
  const b = odds - 1;
  const k = ((b * p - (1 - p)) / b) * 100;
  return Math.max(0, k).toFixed(2);
}

function grade(score) {
  if (score >= 90) return "★★★★★ 강추천";
  if (score >= 82) return "★★★★ 추천";
  if (score >= 75) return "★★★ 관찰";
  return "보류";
}

function sharpScore(p) {
  const score = Number(p.score || 0);
  const drop = Number(p.drop_rate ?? dropRate(p.open_odds, p.odds) ?? 0);
  return Math.min(99, Math.round(score * 0.75 + drop * 3));
}

function confidenceBar(score) {
  const safeScore = Math.max(0, Math.min(100, Number(score || 0)));
  return `
    <div class="meter">
      <div class="meter-fill" style="width:${safeScore}%"></div>
    </div>
    <small>AI 신뢰도 ${safeScore}%</small>
  `;
}

function rankIcon(index) {
  if (index === 0) return "🥇";
  if (index === 1) return "🥈";
  if (index === 2) return "🥉";
  return `#${index + 1}`;
}

function renderGames(games) {
  if (!games || games.length === 0) {
    resultsEl.innerHTML = "<div class='card'>조건에 맞는 경기가 없습니다.</div>";
    return;
  }

  resultsEl.innerHTML = games.map(game => `
    <article class="card">
      <div class="tag">${game.sport || ""} · ${game.league || ""}</div>
      <h2>${game.home || "-"} vs ${game.away || "-"}</h2>
      <p>시작시간: ${game.starts_at || "-"}</p>

      ${(game.markets || []).map(m => `
        <div class="market">
          <b>${m.pick || "-"}</b>
          <span>현재배당 ${m.odds ?? "-"}</span>
          <span>초기배당 ${m.open_odds ?? "-"}</span>
          <span>하락률 ${dropRate(m.open_odds, m.odds)}%</span>
        </div>
      `).join("")}
    </article>
  `).join("");
}

async function loadGames() {
  try {
    setStatus("오늘 경기 불러오는 중...");
    const res = await fetch(`/api/live-games?${params()}`);
    const data = await res.json();

    setStatus(data.notice || `총 ${data.count || 0}경기`);
    renderGames(data.games);
  } catch (err) {
    console.error(err);
    resultsEl.innerHTML = "<div class='card'>경기를 불러오지 못했습니다.</div>";
  }
}

async function analyze() {
  try {
    setStatus("AI 분석 중...");
    const res = await fetch(`/api/recommendations?${params()}`);
    const data = await res.json();

    const combos = data.combos || data.recommendations || [];
    setStatus(data.notice || "AI 분석 완료");

    if (combos.length === 0) {
      resultsEl.innerHTML = "<div class='card'>추천 결과가 없습니다.</div>";
      return;
    }

    resultsEl.innerHTML = combos.map(combo => `
      <article class="card highlight">
        <h2>${combo.type || "추천 조합"}</h2>

        <div class="summary-grid">
          <div><small>총배당</small><b>${combo.total_odds ?? "-"}</b></div>
          <div><small>평균점수</small><b>${combo.avg_score ?? "-"}</b></div>
          <div><small>추천수</small><b>${(combo.picks || []).length}</b></div>
        </div>

        ${(combo.picks || []).map((p, index) => {
          const score = Number(p.score || 0);
          const odds = Number(p.odds || 0);
          const openOdds = Number(p.open_odds || 0);
          const drop = p.drop_rate ?? dropRate(openOdds, odds);
          const evValue = ev(score, odds);
          const sharp = sharpScore(p);

          return `
            <div class="pick">
              <div class="rank">${rankIcon(index)} 추천순위 ${index + 1}</div>
              <div class="tag">${p.type || p.risk || ""}</div>

              <h3>${p.game || `${p.home || "-"} vs ${p.away || "-"}`}</h3>

              ${confidenceBar(score)}

              <p><b>추천: ${p.pick || "-"}</b></p>
              <p>등급: <b>${grade(score)}</b></p>

              <div class="summary-grid">
                <div><small>현재배당</small><b>${odds || "-"}</b></div>
                <div><small>초기배당</small><b>${openOdds || "-"}</b></div>
                <div><small>하락률</small><b>${drop}%</b></div>
                <div><small>암시확률</small><b>${impliedProb(odds)}%</b></div>
                <div><small>EV</small><b>${evValue}%</b></div>
                <div><small>Kelly</small><b>${kelly(score, odds)}%</b></div>
                <div><small>Sharp</small><b>${sharp}점</b></div>
                <div><small>위험도</small><b>${p.risk ?? "-"}</b></div>
              </div>

              <p class="reason">${(p.reasons || []).join(" · ")}</p>
            </div>
          `;
        }).join("")}
      </article>
    `).join("");

  } catch (err) {
    console.error(err);
    resultsEl.innerHTML = "<div class='card'>AI 분석 실패</div>";
  }
}

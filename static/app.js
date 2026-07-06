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
  const prob = score / 100;
  return ((prob * odds - 1) * 100).toFixed(2);
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

async function loadGames() {
  try {
    setStatus("오늘 경기 불러오는 중...");
    const res = await fetch(`/api/live-games?${params()}`);
    const data = await res.json();

    setStatus(data.notice || `총 ${data.count || 0}경기`);

    resultsEl.innerHTML = (data.games || []).map(game => `
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
    `).join("") || "<div class='card'>조건에 맞는 경기가 없습니다.</div>";
  } catch (err) {
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

    resultsEl.innerHTML = combos.map(combo => `
      <article class="card highlight">
        <h2>${combo.type || "추천 조합"}</h2>
        <p>총배당 <b>${combo.total_odds ?? "-"}</b> / 평균점수 <b>${combo.avg_score ?? "-"}</b></p>

        ${(combo.picks || []).map(p => `
          <div class="pick">
            <div class="tag">${p.type || p.risk || ""}</div>
            <h3>${p.game || `${p.home || "-"} vs ${p.away || "-"}`}</h3>

            <p><b>추천: ${p.pick || "-"}</b></p>
            <p>등급: <b>${grade(p.score || 0)}</b></p>

            <p>현재배당 ${p.odds ?? "-"} / 초기배당 ${p.open_odds ?? "-"}</p>
            <p>하락률 ${p.drop_rate ?? dropRate(p.open_odds, p.odds)}% / 점수 ${p.score ?? "-"}</p>
            <p>암시확률 ${impliedProb(p.odds)}% / EV ${ev(p.score, p.odds)}%</p>
            <p>Kelly 기준 ${kelly(p.score, p.odds)}%</p>
            <p>위험도 ${p.risk ?? "-"}</p>

            <p class="reason">${(p.reasons || []).join(" · ")}</p>
          </div>
        `).join("")}
      </article>
    `).join("") || "<div class='card'>추천 결과가 없습니다.</div>";
  } catch (err) {
    resultsEl.innerHTML = "<div class='card'>AI 분석 실패</div>";
  }
}

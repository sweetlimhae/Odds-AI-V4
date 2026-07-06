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

async function loadGames() {
  resultsEl.innerHTML = "<div class='card'>오늘 경기 불러오는 중...</div>";
  const res = await fetch(`/api/live-games?${params()}`);
  const data = await res.json();
  setStatus(data.meta?.notice || `모드: ${data.meta?.mode || "unknown"}`);

  if (!data.games || data.games.length === 0) {
    resultsEl.innerHTML = "<div class='card'>조건에 맞는 경기가 없습니다.</div>";
    return;
  }

  resultsEl.innerHTML = data.games.map(game => `
    <article class="card">
      <div class="tag">${game.sport} · ${game.league}</div>
      <h2>${game.home} vs ${game.away}</h2>
      <p>시작까지 ${game.start_in_minutes ?? "-"}분</p>
      <div class="markets">
        ${(game.markets || []).slice(0, 6).map(m => `<span>${m.pick} ${m.odds} <small>${m.bookmaker || ""}</small></span>`).join("")}
      </div>
    </article>
  `).join("");
}

async function analyze() {
  resultsEl.innerHTML = "<div class='card'>AI 분석 중...</div>";
  const res = await fetch(`/api/recommendations?${params()}`);
  const data = await res.json();
  setStatus(data.meta?.notice || data.notice || `모드: ${data.meta?.mode || "unknown"}`);

  let html = "";
  for (const combo of data.recommendations || []) {
    html += `
      <article class="card highlight">
        <h2>${combo.type}</h2>
        <div class="score-row">
          <b>총배당 ${combo.total_odds}</b>
          <b>평균점수 ${combo.avg_score}</b>
        </div>
        ${(combo.picks || []).map(p => `
          <div class="pick">
            <div class="tag">${p.sport} · ${p.league}</div>
            <h3>${p.home} vs ${p.away}</h3>
            <p><b>추천:</b> ${p.pick}</p>
            <p><b>배당:</b> ${p.odds} / <b>점수:</b> ${p.score} / <b>북:</b> ${p.bookmaker || "-"}</p>
            <p class="reason">${(p.reasons || []).join(" · ")}</p>
          </div>
        `).join("")}
      </article>
    `;
  }

  if (data.excluded && data.excluded.length) {
    html += `<article class="card danger"><h2>제외 경기</h2>${data.excluded.map(g => `<p>${g.league} | ${g.home} vs ${g.away} - ${g.reason}</p>`).join("")}</article>`;
  }

  resultsEl.innerHTML = html || "<div class='card'>추천 결과가 없습니다.</div>";
}

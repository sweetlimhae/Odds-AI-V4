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

function renderGames(games) {
  if (!games || games.length === 0) {
    resultsEl.innerHTML =
      "<div class='card'>조건에 맞는 경기가 없습니다.</div>";
    return;
  }

  resultsEl.innerHTML = games.map(game => `
    <article class="card">
      <div class="tag">${game.sport || ""} · ${game.league}</div>
      <h2>${game.home} vs ${game.away}</h2>
      <p>시작시간 : ${game.starts_at || "-"}</p>

      <div class="markets">
        ${(game.markets || []).map(m => `
          <div class="market">
            <b>${m.pick}</b>
            <span>배당 ${m.odds}</span>
          </div>
        `).join("")}
      </div>
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
    resultsEl.innerHTML =
      "<div class='card'>경기를 불러오지 못했습니다.</div>";
  }
}

async function analyze() {
  try {
    setStatus("AI 분석 중...");

    const res = await fetch(`/api/recommendations?${params()}`);
    const data = await res.json();

    console.log(data);

    // combos 또는 recommendations 둘 다 지원
    const combos = data.combos || data.recommendations || [];

    setStatus(data.notice || "AI 분석 완료");

    if (combos.length === 0) {
      resultsEl.innerHTML =
        "<div class='card'>추천 결과가 없습니다.</div>";
      return;
    }

    resultsEl.innerHTML = combos.map(combo => `
      <article class="card highlight">
        <h2>${combo.type || "추천 조합"}</h2>

        <p>
          총배당 <b>${combo.total_odds ?? "-"}</b>
          /
          평균점수 <b>${combo.avg_score ?? "-"}</b>
        </p>

        ${(combo.picks || []).map(p => `
          <div class="pick">
            <div class="tag">${p.league}</div>

            <h3>${p.home} vs ${p.away}</h3>

            <p><b>${p.pick}</b></p>

            <p>배당 ${p.odds}</p>

            <p>점수 ${p.score}</p>

            <p>${(p.reasons || []).join(" · ")}</p>

          </div>
        `).join("")}

      </article>
    `).join("");

  } catch (err) {
    console.error(err);
    resultsEl.innerHTML =
      "<div class='card'>AI 분석 실패</div>";
  }
}

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

function n(v, fallback = 0) {
  const x = Number(v);
  return Number.isFinite(x) ? x : fallback;
}

function dropRate(openOdds, odds) {
  openOdds = n(openOdds);
  odds = n(odds);
  if (!openOdds || !odds) return "-";
  return (((openOdds - odds) / openOdds) * 100).toFixed(2);
}

function impliedProb(odds) {
  odds = n(odds);
  if (!odds) return "-";
  return ((1 / odds) * 100).toFixed(1);
}

function valueGap(score, odds) {
  score = n(score);
  odds = n(odds);
  if (!score || !odds) return "-";
  return ((score - (100 / odds))).toFixed(1);
}

function ev(score, odds) {
  score = n(score);
  odds = n(odds);
  if (!score || !odds) return "-";
  return (((score / 100) * odds - 1) * 100).toFixed(2);
}

function kelly(score, odds) {
  score = n(score);
  odds = n(odds);
  if (!score || odds <= 1) return "-";
  const p = score / 100;
  const b = odds - 1;
  return Math.max(0, ((b * p - (1 - p)) / b) * 100).toFixed(2);
}

function grade(score) {
  score = n(score);
  if (score >= 92) return "★★★★★ 강추천";
  if (score >= 85) return "★★★★ 추천";
  if (score >= 75) return "★★★ 관찰";
  return "보류";
}

function rankIcon(i) {
  if (i === 0) return "🥇";
  if (i === 1) return "🥈";
  if (i === 2) return "🥉";
  return `#${i + 1}`;
}

function confidenceBar(score) {
  score = Math.max(0, Math.min(100, n(score)));
  return `
    <div class="meter">
      <div class="meter-fill" style="width:${score}%"></div>
    </div>
    <small>AI 신뢰도 ${score}%</small>
  `;
}

function stakeGuide(score, odds) {
  const k = n(kelly(score, odds));
  if (k >= 30) return "실전 추천 비중 15~20%";
  if (k >= 15) return "실전 추천 비중 8~12%";
  if (k >= 5) return "실전 추천 비중 3~5%";
  return "소액 또는 관찰";
}

function aiComment(p) {
  const comments = [];
  const d = n(p.drop_rate ?? dropRate(p.open_odds, p.odds));
  const evv = n(ev(p.score, p.odds));

  if (d >= 5) comments.push("강한 배당 하락");
  else if (d >= 2) comments.push("배당 하락 감지");

  if (n(p.sharp_score) >= 25) comments.push("Sharp 신호 우수");
  if (n(p.steam_score) >= 15) comments.push("Steam Move 감지");
  if (n(p.clv_score) >= 10) comments.push("CLV 기대");
  if (evv > 10) comments.push("EV 우수");
  if (n(p.score) >= 85) comments.push("AI 고점수");

  return comments.length ? comments.join(" · ") : "관찰 필요";
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
          <span>북메이커 ${m.bookmaker || "-"}</span>
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

    if (!combos.length) {
      resultsEl.innerHTML = "<div class='card'>추천 결과가 없습니다.</div>";
      return;
    }

    resultsEl.innerHTML = combos.map(combo => `
      <article class="card highlight">
        <h2>${combo.type || "추천 조합"}</h2>

        <div class="summary-grid">
          <div><small>총배당</small><b>${combo.total_odds ?? "-"}</b></div>
          <div><small>평균점수</small><b>${combo.avg_score ?? "-"}</b></div>
          <div><small>평균EV</small><b>${combo.avg_ev ?? "-"}%</b></div>
          <div><small>평균Kelly</small><b>${combo.avg_kelly ?? "-"}%</b></div>
        </div>

        ${(combo.picks || []).map((p, i) => {
          const score = n(p.score);
          const odds = n(p.odds);
          const openOdds = n(p.open_odds);
          const drop = p.drop_rate ?? dropRate(openOdds, odds);

          return `
            <div class="pick">
              <div class="rank">${rankIcon(i)} 추천순위 ${i + 1}</div>
              <div class="tag">${p.type || p.risk || ""}</div>

              <h3>${p.game || `${p.home || "-"} vs ${p.away || "-"}`}</h3>

              ${confidenceBar(score)}

              <p><b>추천: ${p.pick || "-"}</b></p>
              <p>등급: <b>${grade(score)}</b></p>

              <div class="summary-grid">
                <div><small>현재배당</small><b>${odds || "-"}</b></div>
                <div><small>초기배당</small><b>${openOdds || "-"}</b></div>
                <div><small>하락률</small><b>${drop}%</b></div>
                <div><small>시장확률</small><b>${impliedProb(odds)}%</b></div>
                <div><small>AI 예상승률</small><b>${score}%</b></div>
                <div><small>Value</small><b>${valueGap(score, odds)}%</b></div>
                <div><small>EV</small><b>${ev(score, odds)}%</b></div>
                <div><small>Kelly</small><b>${kelly(score, odds)}%</b></div>
                <div><small>Sharp</small><b>${p.sharp_score ?? "-"}점</b></div>
                <div><small>Steam</small><b>${p.steam_score ?? "-"}점</b></div>
                <div><small>CLV</small><b>${p.clv_score ?? "-"}점</b></div>
                <div><small>위험도</small><b>${p.risk ?? "-"}</b></div>
              </div>

              <p class="reason">
                ${(p.reasons || []).join(" · ")}
              </p>

              <p class="reason">
                AI 의견: ${aiComment(p)}
              </p>

              <p class="reason">
                배팅금액 가이드: ${stakeGuide(score, odds)}
              </p>
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

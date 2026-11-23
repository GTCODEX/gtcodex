/* Match Outcome Predictor dashboard — talks to the LeadFinder server's
   /api/predictor/* endpoints (same origin, relative URLs). */

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

const pct = (x) => `${(x * 100).toFixed(1)}%`;

function fillSelect(select, items, value) {
  select.innerHTML = "";
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = item;
    opt.textContent = item;
    select.appendChild(opt);
  }
  if (value && items.includes(value)) select.value = value;
}

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`tab-${tab.dataset.tab}`).classList.add("active");
  });
});

// ---------------------------------------------------------------- data
let DATASETS = [];

function fillDatasetSelect(select, items, value) {
  select.innerHTML = "";
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = `${item.id} — ${item.label} (${item.matches} matches)`;
    select.appendChild(opt);
  }
  if (value && items.some((d) => d.id === value)) select.value = value;
}

async function loadDatasets() {
  DATASETS = await api("/api/predictor/datasets");
  const names = DATASETS.map((d) => d.id);
  // Default to the combined recent seasons: more data, and it actually contains
  // the current campaign.
  const preferred = names.includes("epl_recent") ? "epl_recent" : names[0];
  fillDatasetSelect($("dataset"), DATASETS, preferred);
  fillDatasetSelect($("btDataset"), DATASETS, preferred);
  await loadTeams();
}

async function loadTeams() {
  const ds = $("dataset").value;
  const info = DATASETS.find((d) => d.id === ds);
  const teams = info ? info.teams : [];
  const home = $("home").value, away = $("away").value;
  fillSelect($("home"), teams, teams[0]);
  fillSelect($("away"), teams, teams[1] || teams[0]);
  if (teams.includes(home)) $("home").value = home;
  if (teams.includes(away) && away !== $("home").value) $("away").value = away;
}

$("dataset").addEventListener("change", loadTeams);

// ---------------------------------------------------------------- predict
function readOdds() {
  const h = parseFloat($("oddsH").value);
  const d = parseFloat($("oddsD").value);
  const a = parseFloat($("oddsA").value);
  if ([h, d, a].every(Number.isFinite) && [h, d, a].every((x) => x > 1)) return [h, d, a];
  return null;
}

function statCard(key, value) {
  return `<div class="stat"><div class="k">${key}</div><div class="v">${value}</div></div>`;
}

function renderPrediction(pred) {
  $("fixture").textContent = `${pred.home} vs ${pred.away}`;
  $("confidence").textContent = `${pred.most_likely_outcome} · ${(pred.confidence * 100).toFixed(1)}% confident`;

  $("homeName").textContent = pred.home;
  $("awayName").textContent = pred.away;
  [["H", pred.home_win, "barH", "valH"],
   ["D", pred.draw, "barD", "valD"],
   ["A", pred.away_win, "barA", "valA"]].forEach(([k, p, bar, val]) => {
    $(bar).style.width = `${(p * 100).toFixed(1)}%`;
    $(val).textContent = pct(p);
  });

  $("statGrid").innerHTML =
    statCard("Expected goals", `${pred.expected_home_goals} - ${pred.expected_away_goals}`) +
    statCard("Most likely score", `${pred.most_likely_score} (${pct(pred.most_likely_prob)})`) +
    statCard("Over 2.5", pct(pred.over_2_5)) +
    statCard("Under 2.5", pct(pred.under_2_5)) +
    statCard("Both teams score", pct(pred.btts)) +
    statCard("Model agreement", pred.model_agreement.toFixed(2));

  if (pred.advice) {
    $("advice").textContent = pred.advice;
    $("advice").hidden = false;
  } else {
    $("advice").hidden = true;
  }
  $("meta").textContent = `Signals used: ${pred.source}` +
    (pred.log_id ? `   ·   logged as ${pred.log_id}` : "");
  $("result").hidden = false;
}

$("predictBtn").addEventListener("click", async () => {
  const err = $("predictError");
  err.hidden = true;
  const payload = {
    dataset: $("dataset").value,
    home: $("home").value,
    away: $("away").value,
    log: $("saveLog").checked,
  };
  const odds = readOdds();
  if (odds) payload.odds = odds;
  if (payload.home === payload.away) {
    err.textContent = "Pick two different teams.";
    err.hidden = false;
    return;
  }
  const btn = $("predictBtn");
  btn.disabled = true;
  try {
    renderPrediction(await api("/api/predictor/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }));
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------- backtest
function renderBacktest(rep) {
  $("btStats").innerHTML =
    statCard("1X2 accuracy", pct(rep.accuracy)) +
    statCard("95% confidence", `${pct(rep.accuracy_ci[0])} – ${pct(rep.accuracy_ci[1])}`) +
    statCard("Log-loss", rep.log_loss.toFixed(4)) +
    statCard("Brier score", rep.brier.toFixed(4)) +
    statCard("ROC-AUC", rep.roc_auc.toFixed(3)) +
    statCard("Over/under 2.5", rep.over_2_5_accuracy == null ? "—" : pct(rep.over_2_5_accuracy));

  const tbody = $("calTable").querySelector("tbody");
  tbody.innerHTML = "";
  rep.calibration.filter((r) => r.n).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${r.bin[0].toFixed(1)}–${r.bin[1].toFixed(1)}</td>` +
      `<td>${r.n}</td><td>${r.mean_pred.toFixed(2)}</td><td>${r.observed.toFixed(2)}</td>`;
    tbody.appendChild(tr);
  });

  const vs = rep.vs_market || {};
  $("btMarket").textContent = vs.n
    ? `Against the betting market on the same ${vs.n} matches: model log-loss ` +
      `${vs.model_log_loss.toFixed(4)} vs market ${vs.market_log_loss.toFixed(4)}.`
    : "";
  $("btResult").hidden = false;
}

$("backtestBtn").addEventListener("click", async () => {
  const err = $("btError");
  err.hidden = true;
  const btn = $("backtestBtn");
  btn.disabled = true;
  $("btRunning").hidden = false;
  try {
    renderBacktest(await api("/api/predictor/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset: $("btDataset").value }),
    }));
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
    $("btRunning").hidden = true;
  }
});

// ---------------------------------------------------------------- forecast log
function renderLog(data) {
  const s = data.score;
  const cards = [
    ["Settled", `${s.n} of ${data.records.length}`],
    ["Awaiting result", s.pending],
    ["1X2 accuracy", s.accuracy == null ? "—" : pct(s.accuracy)],
    ["95% confidence",
      s.accuracy == null ? "—" : `${pct(s.accuracy_ci[0])} – ${pct(s.accuracy_ci[1])}`],
    ["Log-loss", s.log_loss == null ? "—" : s.log_loss.toFixed(4)],
    ["Brier score", s.brier == null ? "—" : s.brier.toFixed(4)],
    ["Over/under 2.5", s.over_under_accuracy == null ? "—" : pct(s.over_under_accuracy)],
    ["BTTS", s.btts_accuracy == null ? "—" : pct(s.btts_accuracy)],
    ["Calibration ECE", data.ece == null ? "—" : data.ece.toFixed(3)],
  ];
  $("logStats").innerHTML = cards.map(([k, v]) => statCard(k, v)).join("");

  const cal = $("logCal").querySelector("tbody");
  cal.innerHTML = "";
  data.calibration.filter((r) => r.n).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${r.bin[0].toFixed(1)}–${r.bin[1].toFixed(1)}</td>` +
      `<td>${r.n}</td><td>${r.mean_pred.toFixed(2)}</td><td>${r.observed.toFixed(2)}</td>`;
    cal.appendChild(tr);
  });
  $("logScore").hidden = s.n === 0;

  const tbody = $("logTable").querySelector("tbody");
  tbody.innerHTML = "";
  data.records.forEach((r) => {
    const tr = document.createElement("tr");
    const probs = [r.home_win, r.draw, r.away_win];
    const pickLabel = ["H", "D", "A"][probs.indexOf(Math.max(...probs))];
    const conf = Math.max(...probs);
    const score = r.home_goals == null ? "—" : `${r.home_goals}-${r.away_goals}`;
    const outcome = r.settled || r.result ? r.result : "—";
    const hit = r.result && pickLabel === r.result ? " ✓" : "";
    tr.innerHTML =
      `<td>${r.fixture_date || r.created_at.slice(0, 10)}</td>` +
      `<td>${r.home} v ${r.away}</td>` +
      `<td>${pickLabel}${hit}</td>` +
      `<td>${(conf * 100).toFixed(0)}%</td>` +
      `<td>${outcome}</td><td>${score}</td><td>${r.status}</td>`;
    tbody.appendChild(tr);
  });
  $("logTableCard").hidden = data.records.length === 0;
}

async function loadLog() {
  try {
    renderLog(await api("/api/predictor/log"));
  } catch (e) {
    $("logError").textContent = e.message;
    $("logError").hidden = false;
  }
}

$("settleBtn").addEventListener("click", async () => {
  const btn = $("settleBtn");
  btn.disabled = true;
  $("logMsg").textContent = "Checking the datasets for results…";
  try {
    const res = await api("/api/predictor/log/settle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    $("logMsg").textContent = res.settled
      ? `Settled ${res.settled} forecast(s).`
      : "No new results found yet — the upstream data may not have caught up.";
    await loadLog();
  } catch (e) {
    $("logError").textContent = e.message;
    $("logError").hidden = false;
  } finally {
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------- init
loadDatasets().catch((e) => {
  const err = $("predictError");
  err.textContent = "Could not load datasets: " + e.message;
  err.hidden = false;
});
loadLog();

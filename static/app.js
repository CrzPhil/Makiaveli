/* ── Makiaveli Solver — Client ─────────────────────────────────────── */

const SUITS = ["S", "H", "D", "C"];
const SUIT_SYMBOLS = { S: "\u2660", H: "\u2665", D: "\u2666", C: "\u2663" };
const RANK_NAMES = { 1: "A", 11: "J", 12: "Q", 13: "K" };
const RANKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];

function rankStr(r) { return RANK_NAMES[r] || String(r); }
function cardCode(rank, suit) { return rankStr(rank) + suit; }
function cardDisplay(rank, suit) { return rankStr(rank) + SUIT_SYMBOLS[suit]; }
function isRed(suit) { return suit === "H" || suit === "D"; }

/* ── State ────────────────────────────────────────────────────────── */

const state = {
  hand: [],            // [{rank, suit}, ...]
  cross: [],           // [{rank, suit}, ...]
  floorGroups: [[]],   // [  [{rank, suit}, ...], ... ]
  activeTarget: "hand",
  solution: null,
  currentStep: 0,
};

// Card count tracking: counts[rank-1][suitIdx] = number assigned
function freshCounts() { return RANKS.map(() => SUITS.map(() => 0)); }
let counts = freshCounts();

function suitIdx(s) { return SUITS.indexOf(s); }

function recountAll() {
  counts = freshCounts();
  const add = (c) => { counts[c.rank - 1][suitIdx(c.suit)]++; };
  state.hand.forEach(add);
  state.cross.forEach(add);
  state.floorGroups.forEach((g) => g.forEach(add));
}

function totalCount(rank, suit) {
  return counts[rank - 1][suitIdx(suit)];
}

/* ── Target helpers ───────────────────────────────────────────────── */

function getActiveList() {
  if (state.activeTarget === "hand") return state.hand;
  if (state.activeTarget === "cross") return state.cross;
  const m = state.activeTarget.match(/^floor-(\d+)$/);
  if (m) return state.floorGroups[parseInt(m[1])];
  return null;
}

function targetColorClass() {
  if (state.activeTarget === "hand") return "hand";
  if (state.activeTarget === "cross") return "cross";
  return "floor";
}

/* ── Client-side validation ───────────────────────────────────────── */

function isValidSet(cards) {
  if (cards.length < 3) return false;
  const ranks = new Set(cards.map((c) => c.rank));
  const suits = new Set(cards.map((c) => c.suit));
  return ranks.size === 1 && suits.size === cards.length;
}

function isValidRun(cards) {
  if (cards.length < 3) return false;
  const suits = new Set(cards.map((c) => c.suit));
  if (suits.size !== 1) return false;
  const ranks = cards.map((c) => c.rank).sort((a, b) => a - b);
  const unique = new Set(ranks);
  if (unique.size !== ranks.length) return false;
  // Normal consecutive
  let consecutive = true;
  for (let i = 0; i < ranks.length - 1; i++) {
    if (ranks[i] + 1 !== ranks[i + 1]) { consecutive = false; break; }
  }
  if (consecutive) return true;
  // Ace-high
  if (ranks.includes(1) && ranks.includes(13)) {
    const high = ranks.map((r) => r === 1 ? 14 : r).sort((a, b) => a - b);
    for (let i = 0; i < high.length - 1; i++) {
      if (high[i] + 1 !== high[i + 1]) return false;
    }
    return true;
  }
  return false;
}

function isValidGroup(cards) {
  return isValidSet(cards) || isValidRun(cards);
}

/* ── DOM refs ─────────────────────────────────────────────────────── */

const $grid = document.getElementById("card-grid");
const $tabs = document.getElementById("target-tabs");
const $addGroupBtn = document.getElementById("add-group-btn");
const $chipsLabel = document.getElementById("chips-label");
const $chipsList = document.getElementById("chips-list");
const $summary = document.getElementById("summary-content");
const $solveBtn = document.getElementById("solve-btn");
const $clearBtn = document.getElementById("clear-btn");
const $solutionSection = document.getElementById("solution-section");
const $solutionMeta = document.getElementById("solution-meta");
const $stepPrev = document.getElementById("step-prev");
const $stepNext = document.getElementById("step-next");
const $stepIndicator = document.getElementById("step-indicator");
const $stepDesc = document.getElementById("step-description");
const $targetLayout = document.getElementById("target-layout");
const $remainingCross = document.getElementById("remaining-cross");

/* ── Build Grid ───────────────────────────────────────────────────── */

function buildGrid() {
  $grid.innerHTML = "";
  // Rows: S, H, D, C.  Columns: A, 2..10, J, Q, K
  for (const suit of SUITS) {
    for (const rank of RANKS) {
      const cell = document.createElement("div");
      cell.className = "grid-cell " + (isRed(suit) ? "red" : "black");
      cell.dataset.rank = rank;
      cell.dataset.suit = suit;
      cell.innerHTML =
        `<span class="rank">${rankStr(rank)}</span>` +
        `<span class="suit">${SUIT_SYMBOLS[suit]}</span>` +
        `<div class="assign-dots"></div>`;
      cell.addEventListener("click", () => onGridClick(rank, suit));
      $grid.appendChild(cell);
    }
  }
}

/* ── Grid click ───────────────────────────────────────────────────── */

function onGridClick(rank, suit) {
  if (totalCount(rank, suit) >= 2) return; // 2-deck max
  const list = getActiveList();
  if (!list) return;
  list.push({ rank, suit });
  counts[rank - 1][suitIdx(suit)]++;
  hideSolution();
  renderAll();
}

/* ── Remove card ──────────────────────────────────────────────────── */

function removeCard(target, index) {
  let list;
  if (target === "hand") list = state.hand;
  else if (target === "cross") list = state.cross;
  else {
    const m = target.match(/^floor-(\d+)$/);
    if (m) list = state.floorGroups[parseInt(m[1])];
  }
  if (!list) return;
  const card = list[index];
  list.splice(index, 1);
  counts[card.rank - 1][suitIdx(card.suit)]--;
  hideSolution();
  renderAll();
}

/* ── Tabs ─────────────────────────────────────────────────────────── */

function addFloorGroup() {
  state.floorGroups.push([]);
  state.activeTarget = "floor-" + (state.floorGroups.length - 1);
  hideSolution();
  renderAll();
}

function removeFloorGroup(idx) {
  const group = state.floorGroups[idx];
  group.forEach((c) => { counts[c.rank - 1][suitIdx(c.suit)]--; });
  state.floorGroups.splice(idx, 1);
  // Fix active target
  if (state.activeTarget === "floor-" + idx) {
    state.activeTarget = "hand";
  } else {
    const m = state.activeTarget.match(/^floor-(\d+)$/);
    if (m && parseInt(m[1]) > idx) {
      state.activeTarget = "floor-" + (parseInt(m[1]) - 1);
    }
  }
  hideSolution();
  renderAll();
}

function setActiveTarget(target) {
  state.activeTarget = target;
  renderAll();
}

/* ── Render ────────────────────────────────────────────────────────── */

function renderAll() {
  renderTabs();
  renderGrid();
  renderChips();
  renderSummary();
  $solveBtn.disabled = state.hand.length === 0;
}

function renderTabs() {
  // Remove old dynamic tabs
  $tabs.querySelectorAll(".tab-dynamic").forEach((t) => t.remove());

  // Update hand/cross tabs
  $tabs.querySelectorAll(".tab[data-target]").forEach((t) => {
    t.classList.toggle("active", t.dataset.target === state.activeTarget);
  });

  // Insert floor group tabs before the add button
  state.floorGroups.forEach((group, i) => {
    const tab = document.createElement("button");
    tab.className = "tab tab-dynamic";
    tab.dataset.target = "floor-" + i;
    if (state.activeTarget === "floor-" + i) tab.classList.add("active");

    let label = `Floor #${i + 1}`;
    if (group.length > 0) {
      label += `<span class="badge">(${group.length})</span>`;
      const valid = isValidGroup(group);
      label += `<span class="validity">${valid ? "\u2713" : "\u26A0"}</span>`;
    }
    if (state.floorGroups.length > 1 || group.length > 0) {
      label += `<span class="remove-group" data-group-idx="${i}">\u2715</span>`;
    }

    tab.innerHTML = label;
    tab.addEventListener("click", (e) => {
      if (e.target.classList.contains("remove-group")) {
        e.stopPropagation();
        removeFloorGroup(parseInt(e.target.dataset.groupIdx));
        return;
      }
      setActiveTarget("floor-" + i);
    });

    $tabs.insertBefore(tab, $addGroupBtn);
  });
}

function renderGrid() {
  // Build assignment map: "rank-suit" -> [{type, groupIdx?}, ...]
  const assigns = {};
  const key = (r, s) => r + "-" + s;

  state.hand.forEach((c) => {
    const k = key(c.rank, c.suit);
    (assigns[k] = assigns[k] || []).push({ type: "hand" });
  });
  state.cross.forEach((c) => {
    const k = key(c.rank, c.suit);
    (assigns[k] = assigns[k] || []).push({ type: "cross" });
  });
  state.floorGroups.forEach((g, gi) => {
    g.forEach((c) => {
      const k = key(c.rank, c.suit);
      (assigns[k] = assigns[k] || []).push({ type: "floor", groupIdx: gi });
    });
  });

  $grid.querySelectorAll(".grid-cell").forEach((cell) => {
    const r = parseInt(cell.dataset.rank);
    const s = cell.dataset.suit;
    const k = key(r, s);
    const a = assigns[k] || [];
    const total = a.length;

    cell.classList.toggle("dimmed", total >= 2);

    const dots = cell.querySelector(".assign-dots");
    dots.innerHTML = "";
    a.forEach((entry) => {
      const dot = document.createElement("span");
      dot.className = "assign-dot " + entry.type;
      dots.appendChild(dot);
    });
  });
}

function renderChips() {
  const list = getActiveList();
  const target = state.activeTarget;
  const color = targetColorClass();

  if (!list) { $chipsList.innerHTML = ""; $chipsLabel.textContent = ""; return; }

  let label = target === "hand" ? "Hand" : target === "cross" ? "Cross" : "";
  if (target.startsWith("floor-")) {
    label = "Floor #" + (parseInt(target.split("-")[1]) + 1);
  }
  $chipsLabel.textContent = list.length > 0 ? `${label} (${list.length}) — click to remove:` : `${label} — click grid to add cards`;

  $chipsList.innerHTML = "";
  list.forEach((card, i) => {
    const chip = document.createElement("span");
    chip.className = "chip " + color;
    chip.innerHTML = `${cardDisplay(card.rank, card.suit)} <span class="remove">\u2715</span>`;
    chip.addEventListener("click", () => removeCard(target, i));
    $chipsList.appendChild(chip);
  });
}

function renderSummary() {
  let html = "";

  // Hand
  html += `<div class="summary-row">`;
  html += `<span class="summary-label">Hand (${state.hand.length}):</span>`;
  html += `<span class="summary-cards">`;
  if (state.hand.length === 0) html += `<span style="color:var(--text-dim)">(empty)</span>`;
  else state.hand.forEach((c) => {
    html += `<span class="summary-card ${isRed(c.suit) ? "red" : "black"}">${cardDisplay(c.rank, c.suit)}</span> `;
  });
  html += `</span></div>`;

  // Cross
  html += `<div class="summary-row">`;
  html += `<span class="summary-label">Cross (${state.cross.length}):</span>`;
  html += `<span class="summary-cards">`;
  if (state.cross.length === 0) html += `<span style="color:var(--text-dim)">(none)</span>`;
  else state.cross.forEach((c) => {
    html += `<span class="summary-card ${isRed(c.suit) ? "red" : "black"}">${cardDisplay(c.rank, c.suit)}</span> `;
  });
  html += `</span></div>`;

  // Floor groups
  state.floorGroups.forEach((group, i) => {
    if (group.length === 0 && state.floorGroups.length === 1) return;
    const valid = group.length > 0 ? isValidGroup(group) : null;
    const vMark = valid === null ? "" : valid ? " \u2713" : " \u26A0";
    html += `<div class="summary-row">`;
    html += `<span class="summary-label">Floor #${i + 1}${vMark}:</span>`;
    html += `<span class="summary-cards">`;
    if (group.length === 0) html += `<span style="color:var(--text-dim)">(empty)</span>`;
    else group.forEach((c) => {
      html += `<span class="summary-card ${isRed(c.suit) ? "red" : "black"}">${cardDisplay(c.rank, c.suit)}</span> `;
    });
    html += `</span></div>`;
  });

  const totalCards = state.hand.length + state.cross.length +
    state.floorGroups.reduce((s, g) => s + g.length, 0);
  html += `<div class="summary-row" style="margin-top:0.3rem">`;
  html += `<span class="summary-label">Total cards:</span>`;
  html += `<span>${totalCards}</span></div>`;

  $summary.innerHTML = html;
}

/* ── Solve ─────────────────────────────────────────────────────────── */

async function solve() {
  $solveBtn.disabled = true;
  $solveBtn.textContent = "Solving...";
  $solveBtn.classList.add("loading");

  const body = {
    hand: state.hand.map((c) => cardCode(c.rank, c.suit)),
    cross: state.cross.map((c) => cardCode(c.rank, c.suit)),
    floor_groups: state.floorGroups
      .filter((g) => g.length > 0)
      .map((g) => g.map((c) => cardCode(c.rank, c.suit))),
  };

  try {
    const resp = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    if (data.error) {
      alert("Error: " + data.error);
      return;
    }

    state.solution = data;
    state.currentStep = 0;
    showSolution();
  } catch (e) {
    alert("Request failed: " + e.message);
  } finally {
    $solveBtn.disabled = state.hand.length === 0;
    $solveBtn.textContent = "Solve";
    $solveBtn.classList.remove("loading");
  }
}

/* ── Solution display ─────────────────────────────────────────────── */

function showSolution() {
  const sol = state.solution;
  $solutionSection.classList.remove("hidden");

  if (!sol.solvable) {
    $solutionMeta.textContent = `No solution found. (${sol.elapsed_seconds}s)`;
    $stepDesc.textContent = "You cannot empty your hand from this state.";
    $targetLayout.innerHTML = "";
    $remainingCross.innerHTML = "";
    $stepPrev.disabled = true;
    $stepNext.disabled = true;
    $stepIndicator.textContent = "";
    return;
  }

  $solutionMeta.textContent = `Solution found in ${sol.elapsed_seconds}s`;

  // Build card origin map for highlighting
  const handSet = new Set(state.hand.map((c) => cardCode(c.rank, c.suit)));

  // Render target layout
  renderTargetLayout(sol.target_groups, handSet);

  // Render steps
  if (sol.steps.length > 0) {
    state.currentStep = 1;
    renderStep();
  } else {
    $stepIndicator.textContent = "No rearrangement needed";
    $stepDesc.textContent = "Just play your cards!";
    $stepPrev.disabled = true;
    $stepNext.disabled = true;
  }

  // Remaining cross
  if (sol.remaining_cross && sol.remaining_cross.length > 0) {
    $remainingCross.innerHTML = "Cross cards left in place: " +
      sol.remaining_cross.map((c) => {
        const cls = isRed(c.suit) ? "red" : "black";
        return `<span class="summary-card ${cls}">${c.display}</span>`;
      }).join(" ");
  } else {
    $remainingCross.innerHTML = "";
  }

  $solutionSection.scrollIntoView({ behavior: "smooth" });
}

function renderTargetLayout(groups, handSet) {
  $targetLayout.innerHTML = "";

  // Collect all original floor cards for "stayed in place" detection
  const floorCards = {};
  state.floorGroups.forEach((g, gi) => {
    g.forEach((c) => {
      const code = cardCode(c.rank, c.suit);
      (floorCards[code] = floorCards[code] || []).push(gi);
    });
  });

  // Track hand card usage for multi-copy correctness
  const handUsed = {};

  groups.forEach((group, gi) => {
    const div = document.createElement("div");
    div.className = "target-group";
    div.innerHTML = `<span class="target-group-label">[${gi}]</span>`;

    group.forEach((card) => {
      const box = document.createElement("span");
      const cls = isRed(card.suit) ? "red" : "black";
      box.className = "card-box " + cls;
      box.textContent = card.display;

      // Origin highlighting
      const code = card.code;
      const usedKey = code;
      if (handSet.has(code) && (!handUsed[usedKey] || handUsed[usedKey] < countInArray(state.hand, code))) {
        box.classList.add("from-hand");
        handUsed[usedKey] = (handUsed[usedKey] || 0) + 1;
      } else if (floorCards[code] && floorCards[code].length > 0) {
        // Check if it stayed in a matched floor group or moved
        // Simple heuristic: just mark floor-origin cards
        floorCards[code].shift();
      }

      div.appendChild(box);
    });

    $targetLayout.appendChild(div);
  });
}

function countInArray(arr, code) {
  return arr.filter((c) => cardCode(c.rank, c.suit) === code).length;
}

function renderStep() {
  const sol = state.solution;
  const total = sol.steps.length;
  const idx = state.currentStep;

  $stepIndicator.textContent = `Step ${idx} of ${total}`;
  $stepPrev.disabled = idx <= 1;
  $stepNext.disabled = idx >= total;

  if (idx >= 1 && idx <= total) {
    $stepDesc.textContent = sol.steps[idx - 1].description;
  }
}

function stepPrev() {
  if (state.currentStep > 1) { state.currentStep--; renderStep(); }
}

function stepNext() {
  if (state.solution && state.currentStep < state.solution.steps.length) {
    state.currentStep++;
    renderStep();
  }
}

function hideSolution() {
  state.solution = null;
  $solutionSection.classList.add("hidden");
}

/* ── Clear ─────────────────────────────────────────────────────────── */

function clearAll() {
  state.hand = [];
  state.cross = [];
  state.floorGroups = [[]];
  state.activeTarget = "hand";
  counts = freshCounts();
  hideSolution();
  renderAll();
}

/* ── Event listeners ──────────────────────────────────────────────── */

$tabs.querySelector('[data-target="hand"]').addEventListener("click", () => setActiveTarget("hand"));
$tabs.querySelector('[data-target="cross"]').addEventListener("click", () => setActiveTarget("cross"));
$addGroupBtn.addEventListener("click", addFloorGroup);
$solveBtn.addEventListener("click", solve);
$clearBtn.addEventListener("click", clearAll);
$stepPrev.addEventListener("click", stepPrev);
$stepNext.addEventListener("click", stepNext);

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") stepPrev();
  if (e.key === "ArrowRight") stepNext();
});

/* ── Init ──────────────────────────────────────────────────────────── */

buildGrid();
renderAll();

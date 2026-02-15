/* ── Makiaveli Game — Client ─────────────────────────────────────────── */

const SUIT_SYMBOLS = { S: "\u2660", H: "\u2665", D: "\u2666", C: "\u2663" };
const RANK_NAMES = { 1: "A", 11: "J", 12: "Q", 13: "K" };

function rankStr(r) { return RANK_NAMES[r] || String(r); }
function cardDisplay(card) { return rankStr(card.rank) + SUIT_SYMBOLS[card.suit]; }
function isRed(suit) { return suit === "H" || suit === "D"; }
function cardCode(card) { return card.code; }

/* ── State ───────────────────────────────────────────────────────────── */

let gameId = null;
let hand = [];
let floorGroups = [];
let cross = [];       // array of card|null (4 slots)
let deckCount = 0;
let opponentCards = 0;
let currentPlayer = null;
let gameOver = false;
let winner = null;

// Play mode state
let playMode = false;
let staging = [];          // array of arrays of card objects (editable copy)
let selectedCards = [];    // cards selected for placement
let savedHand = null;      // snapshot of hand before play mode

/* ── DOM refs ────────────────────────────────────────────────────────── */

const $botCount = document.getElementById("bot-card-count");
const $botLog = document.getElementById("bot-log");
const $crossSlots = document.getElementById("cross-slots");
const $floorGroups = document.getElementById("floor-groups");
const $deckCount = document.getElementById("deck-count");
const $stagingArea = document.getElementById("staging-area");
const $stagingGroups = document.getElementById("staging-groups");
const $addGroupBtn = document.getElementById("add-group-btn");
const $selectedCards = document.getElementById("selected-cards");
const $handCards = document.getElementById("hand-cards");
const $btnNew = document.getElementById("btn-new");
const $btnDraw = document.getElementById("btn-draw");
const $btnPlayMode = document.getElementById("btn-play-mode");
const $btnEndTurn = document.getElementById("btn-end-turn");
const $btnCancel = document.getElementById("btn-cancel");
const $statusBar = document.getElementById("status-bar");
const $overlay = document.getElementById("game-over-overlay");
const $overMsg = document.getElementById("game-over-msg");
const $btnPlayAgain = document.getElementById("btn-play-again");

/* ── API helpers ─────────────────────────────────────────────────────── */

async function apiPost(path, body) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || resp.statusText);
  }
  return resp.json();
}

async function apiGet(path) {
  const resp = await fetch(path);
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || resp.statusText);
  }
  return resp.json();
}

/* ── State management ────────────────────────────────────────────────── */

function loadState(data) {
  if (data.game_id) gameId = data.game_id;
  hand = data.hand || [];
  floorGroups = data.floor_groups || [];
  cross = data.cross || [];
  deckCount = data.deck_count || 0;
  opponentCards = data.opponent_card_count || 0;
  currentPlayer = data.current_player;
  gameOver = data.game_over || false;
  winner = data.winner || null;
}

function setStatus(msg, isError) {
  $statusBar.textContent = msg;
  $statusBar.className = isError ? "error" : "";
}

/* ── Card rendering ──────────────────────────────────────────────────── */

function makeCardEl(card, extraClass) {
  const el = document.createElement("div");
  let cls = "game-card " + (isRed(card.suit) ? "red" : "black");
  if (extraClass) cls += " " + extraClass;
  el.className = cls;
  el.innerHTML = `<span class="rank">${rankStr(card.rank)}</span><span class="suit">${SUIT_SYMBOLS[card.suit]}</span>`;
  el.dataset.code = card.code;
  return el;
}

function makeCrossSlot(card) {
  if (card === null) {
    const el = document.createElement("div");
    el.className = "game-card cross-empty";
    el.innerHTML = `<span class="rank">-</span><span class="suit">-</span>`;
    return el;
  }
  return makeCardEl(card, "cross-card");
}

/* ── Render ───────────────────────────────────────────────────────────── */

function render() {
  renderBot();
  renderTable();
  renderHand();
  renderButtons();
  if (playMode) renderStaging();
  if (gameOver) showGameOver();
}

function renderBot() {
  $botCount.textContent = `Cards: ${opponentCards}`;
}

function renderTable() {
  // Cross
  $crossSlots.innerHTML = "";
  cross.forEach(c => $crossSlots.appendChild(makeCrossSlot(c)));

  // Floor
  $floorGroups.innerHTML = "";
  if (floorGroups.length === 0) {
    const empty = document.createElement("span");
    empty.className = "floor-empty";
    empty.textContent = "(empty)";
    $floorGroups.appendChild(empty);
  } else {
    floorGroups.forEach((group, gi) => {
      const div = document.createElement("div");
      div.className = "floor-group";
      const label = document.createElement("span");
      label.className = "floor-group-label";
      label.textContent = `#${gi}`;
      div.appendChild(label);
      group.forEach(card => {
        const el = makeCardEl(card);
        if (playMode) {
          el.addEventListener("click", () => selectFloorCard(gi, card));
        }
        div.appendChild(el);
      });
      $floorGroups.appendChild(div);
    });
  }

  // Deck
  $deckCount.textContent = deckCount;
}

function renderHand() {
  $handCards.innerHTML = "";
  const sorted = [...hand].sort((a, b) => {
    if (a.suit !== b.suit) return a.suit < b.suit ? -1 : 1;
    return a.rank - b.rank;
  });
  sorted.forEach(card => {
    const isSelected = selectedCards.some(s => s.code === card.code && s._idx === card._idx);
    const el = makeCardEl(card, isSelected ? "selected" : "");
    el.addEventListener("click", () => toggleHandCard(card));
    $handCards.appendChild(el);
  });
}

function renderButtons() {
  const isHumanTurn = currentPlayer === "human" && !gameOver;
  if (playMode) {
    $btnDraw.classList.add("hidden");
    $btnPlayMode.classList.add("hidden");
    $btnEndTurn.classList.remove("hidden");
    $btnCancel.classList.remove("hidden");
    $btnEndTurn.disabled = false;
  } else {
    $btnDraw.classList.remove("hidden");
    $btnPlayMode.classList.remove("hidden");
    $btnEndTurn.classList.add("hidden");
    $btnCancel.classList.add("hidden");
    $btnDraw.disabled = !isHumanTurn || deckCount === 0;
    $btnPlayMode.disabled = !isHumanTurn || hand.length === 0;
  }
}

/* ── Staging (play mode) ─────────────────────────────────────────────── */

function enterPlayMode() {
  playMode = true;
  selectedCards = [];
  // Save a deep copy of hand so we can restore on cancel
  savedHand = hand.map(c => ({ ...c }));
  // Copy floor into staging
  staging = floorGroups.map(g => g.map(c => ({ ...c })));
  // Add active cross cards as anchored single-card groups
  cross.forEach((c, i) => {
    if (c !== null) staging.push([{ ...c, _crossSlot: i }]);
  });
  // Tag hand cards with unique indices for selection tracking
  hand.forEach((c, i) => c._idx = i);
  $stagingArea.classList.remove("hidden");
  setStatus("Play mode: select cards from hand, then click a group to place them.");
  render();
}

function exitPlayMode() {
  // Restore hand from saved snapshot (cards may have been moved to staging)
  if (savedHand) {
    hand = savedHand;
    savedHand = null;
  }
  playMode = false;
  selectedCards = [];
  staging = [];
  $stagingArea.classList.add("hidden");
  setStatus("");
  render();
}

function _groupHasCross(group) {
  return group.some(c => c._crossSlot !== undefined);
}

function renderStaging() {
  $stagingGroups.innerHTML = "";
  staging.forEach((group, gi) => {
    const div = document.createElement("div");
    const isCrossGroup = _groupHasCross(group);
    div.className = "staging-group" + (isCrossGroup ? " cross-anchored" : "");

    // Validate
    if (group.length >= 3) {
      const valid = isValidGroup(group);
      div.classList.add(valid ? "valid" : "invalid");
    }

    const label = document.createElement("span");
    label.className = "staging-group-label";
    label.textContent = isCrossGroup ? "\u2693" : `#${gi}`;
    div.appendChild(label);

    group.forEach((card, ci) => {
      const isCrossCard = card._crossSlot !== undefined;
      const isSelected = selectedCards.some(s => s._stagingGroup === gi && s._stagingIdx === ci);
      const extraCls = isCrossCard ? "cross-card" : (isSelected ? "selected" : "");
      const el = makeCardEl(card, extraCls);
      if (!isCrossCard) {
        // Non-cross cards in a group can be selected and moved
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          toggleStagingCard(gi, ci, card);
        });
      }
      div.appendChild(el);
    });

    // Remove group button — not for cross-anchored groups
    if (!isCrossGroup) {
      const removeBtn = document.createElement("span");
      removeBtn.className = "remove-group";
      removeBtn.textContent = "\u2715";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeStagingGroup(gi);
      });
      div.appendChild(removeBtn);
    }

    // Click group to place selected cards
    div.addEventListener("click", () => placeSelectedInGroup(gi));
    $stagingGroups.appendChild(div);
  });

  // Render selected cards display
  $selectedCards.innerHTML = "";
  selectedCards.forEach(card => {
    const el = makeCardEl(card, "selected");
    el.style.width = "40px";
    el.style.height = "56px";
    el.style.fontSize = "0.75rem";
    $selectedCards.appendChild(el);
  });
}

function toggleHandCard(card) {
  if (!playMode) return;
  const idx = selectedCards.findIndex(s => s.code === card.code && s._idx === card._idx && !s._fromStaging);
  if (idx >= 0) {
    selectedCards.splice(idx, 1);
  } else {
    // Deselect any staging selections when selecting hand cards
    selectedCards = selectedCards.filter(s => !s._fromStaging);
    selectedCards.push({ ...card, _fromStaging: false });
  }
  render();
}

function toggleStagingCard(gi, ci, card) {
  if (!playMode) return;
  const idx = selectedCards.findIndex(s => s._fromStaging && s._stagingGroup === gi && s._stagingIdx === ci);
  if (idx >= 0) {
    selectedCards.splice(idx, 1);
  } else {
    // Deselect any hand selections when selecting staging cards
    selectedCards = selectedCards.filter(s => s._fromStaging);
    selectedCards.push({ ...card, _fromStaging: true, _stagingGroup: gi, _stagingIdx: ci });
  }
  render();
}

function selectFloorCard(gi, card) {
  // In play mode, floor is read-only — staging is the editable copy
}

function placeSelectedInGroup(gi) {
  if (selectedCards.length === 0) return;

  const handSelected = selectedCards.filter(s => !s._fromStaging);
  const stagingSelected = selectedCards.filter(s => s._fromStaging);

  // Move staging cards to target group
  if (stagingSelected.length > 0) {
    // Collect cards to move (remove from their source groups, highest index first)
    const toMove = [];
    // Sort by group then index descending so splicing doesn't shift indices
    const sorted = [...stagingSelected].sort((a, b) =>
      a._stagingGroup !== b._stagingGroup
        ? b._stagingGroup - a._stagingGroup
        : b._stagingIdx - a._stagingIdx
    );
    sorted.forEach(s => {
      const removed = staging[s._stagingGroup].splice(s._stagingIdx, 1);
      toMove.push(...removed);
    });
    staging[gi].push(...toMove);
    // Remove empty groups (but not the target; cross groups can't be emptied
    // because the anchored cross card is never selectable)
    staging = staging.filter((g, i) => g.length > 0 || i === gi);
  }

  // Place hand cards
  if (handSelected.length > 0) {
    handSelected.forEach(s => {
      staging[gi].push({ code: s.code, rank: s.rank, suit: s.suit, display: s.display, _fromHand: true });
      // Remove from hand
      const hIdx = hand.findIndex(h => h.code === s.code && h._idx === s._idx);
      if (hIdx >= 0) hand.splice(hIdx, 1);
    });
    // Re-tag hand indices
    hand.forEach((c, i) => c._idx = i);
  }

  selectedCards = [];
  render();
}

function addStagingGroup() {
  staging.push([]);
  render();
}

function removeStagingGroup(gi) {
  const group = staging[gi];
  // Return cards that came from hand back to hand
  group.forEach(c => {
    if (c._fromHand) {
      hand.push({ code: c.code, rank: c.rank, suit: c.suit, display: c.display });
    }
  });
  hand.forEach((c, i) => c._idx = i);
  staging.splice(gi, 1);
  selectedCards = selectedCards.filter(s => !(s._fromStaging && s._stagingGroup === gi));
  // Fix staging group indices in selected
  selectedCards.forEach(s => {
    if (s._fromStaging && s._stagingGroup > gi) s._stagingGroup--;
  });
  render();
}

/* ── Validation (client-side) ────────────────────────────────────────── */

function isValidSet(cards) {
  if (cards.length < 3) return false;
  const ranks = new Set(cards.map(c => c.rank));
  const suits = new Set(cards.map(c => c.suit));
  return ranks.size === 1 && suits.size === cards.length;
}

function isValidRun(cards) {
  if (cards.length < 3) return false;
  const suits = new Set(cards.map(c => c.suit));
  if (suits.size !== 1) return false;
  const ranks = cards.map(c => c.rank).sort((a, b) => a - b);
  if (new Set(ranks).size !== ranks.length) return false;
  let consecutive = true;
  for (let i = 0; i < ranks.length - 1; i++) {
    if (ranks[i] + 1 !== ranks[i + 1]) { consecutive = false; break; }
  }
  if (consecutive) return true;
  if (ranks.includes(1) && ranks.includes(13)) {
    const high = ranks.map(r => r === 1 ? 14 : r).sort((a, b) => a - b);
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

/* ── Actions ─────────────────────────────────────────────────────────── */

async function newGame() {
  try {
    exitPlayMode();
    $overlay.classList.add("hidden");
    $botLog.innerHTML = "";
    setStatus("Starting new game...");
    const data = await apiPost("/api/game/new");
    loadState(data);
    setStatus("Game started! Your turn.");
    render();
  } catch (e) {
    setStatus("Error: " + e.message, true);
  }
}

async function drawCard() {
  try {
    $btnDraw.disabled = true;
    setStatus("Drawing...");
    const data = await apiPost(`/api/game/${gameId}/draw`);
    const drawnCard = data.drawn_card;
    loadState(data);
    if (drawnCard) {
      setStatus(`Drew ${drawnCard.display}. Bot is thinking...`);
    }
    render();
    if (data.bot_move) {
      await animateBotMove(data.bot_move);
      // Reload state after bot
      const updated = await apiGet(`/api/game/${gameId}/state`);
      loadState(updated);
      render();
    }
    if (!gameOver) setStatus("Your turn.");
  } catch (e) {
    setStatus("Error: " + e.message, true);
    render();
  }
}

async function endTurn() {
  // cards_played = savedHand - current hand (cards moved to staging)
  const currentCodes = hand.map(c => c.code);
  const cardsPlayed = [];
  const usedCurrent = new Array(currentCodes.length).fill(false);

  for (const orig of savedHand) {
    let found = false;
    for (let i = 0; i < currentCodes.length; i++) {
      if (!usedCurrent[i] && currentCodes[i] === orig.code) {
        usedCurrent[i] = true;
        found = true;
        break;
      }
    }
    if (!found) cardsPlayed.push(orig.code);
  }

  if (cardsPlayed.length === 0) {
    setStatus("You must play at least 1 card from your hand.", true);
    return;
  }

  // Build floor_groups from staging
  const newFloor = staging
    .filter(g => g.length > 0)
    .map(g => g.map(c => c.code));

  try {
    $btnEndTurn.disabled = true;
    setStatus("Validating...");
    const data = await apiPost(`/api/game/${gameId}/play`, {
      floor_groups: newFloor,
      cards_played: cardsPlayed,
    });
    loadState(data);
    savedHand = null;  // don't restore old hand — play was accepted
    exitPlayMode();
    setStatus("Move accepted! Bot is thinking...");
    render();
    if (data.bot_move) {
      await animateBotMove(data.bot_move);
      const updated = await apiGet(`/api/game/${gameId}/state`);
      loadState(updated);
      render();
    }
    if (!gameOver) setStatus("Your turn.");
  } catch (e) {
    setStatus("Error: " + e.message, true);
    $btnEndTurn.disabled = false;
  }
}

/* ── Bot Animation ───────────────────────────────────────────────────── */

async function animateBotMove(botMove) {
  $botLog.innerHTML = "";
  for (let i = 0; i < botMove.steps.length; i++) {
    await sleep(600);
    const step = document.createElement("div");
    step.className = "bot-step";
    step.textContent = botMove.steps[i];
    step.style.animationDelay = "0s";
    $botLog.appendChild(step);
  }
  await sleep(400);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ── Game Over ───────────────────────────────────────────────────────── */

function showGameOver() {
  $overMsg.textContent = winner === "human" ? "You win!" : "Bot wins!";
  $overlay.classList.remove("hidden");
}

/* ── Event Listeners ─────────────────────────────────────────────────── */

$btnNew.addEventListener("click", newGame);
$btnDraw.addEventListener("click", drawCard);
$btnPlayMode.addEventListener("click", enterPlayMode);
$btnEndTurn.addEventListener("click", endTurn);
$btnCancel.addEventListener("click", exitPlayMode);
$addGroupBtn.addEventListener("click", addStagingGroup);
$btnPlayAgain.addEventListener("click", newGame);

/* ── Init ────────────────────────────────────────────────────────────── */

setStatus('Click "New Game" to start.');
render();

const API = "";
const POLL_MS = 2000;
const TOKEN_KEY_PREFIX = "commander_chess_token_";

let busy = false;
let lastState = null;
let playerColor = null;
let playerToken = null;
let pollTimer = null;
let lobbyPollTimer = null;

function tokenStorageKey(color) {
  return `${TOKEN_KEY_PREFIX}${color}`;
}

function loadStoredToken(color) {
  return sessionStorage.getItem(tokenStorageKey(color));
}

function savePlayerToken(color, token) {
  if (token) {
    sessionStorage.setItem(tokenStorageKey(color), token);
  }
  playerToken = token;
}

function clearPlayerToken(color) {
  if (color) {
    sessionStorage.removeItem(tokenStorageKey(color));
  }
  playerToken = null;
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (playerToken) {
    headers["X-Player-Token"] = playerToken;
  }
  const res = await fetch(`${API}${path}`, {
    headers,
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg = typeof detail === "string" ? detail : data.message || res.statusText;
    throw new Error(msg);
  }
  return data;
}

const els = {
  teamScreen: document.getElementById("team-screen"),
  gameScreen: document.getElementById("game-screen"),
  landingPicker: document.getElementById("landing-picker"),
  sideJoinPanel: document.getElementById("side-join-panel"),
  sideRoleLabel: document.getElementById("side-role-label"),
  sideJoinStatus: document.getElementById("side-join-status"),
  sideRetry: document.getElementById("side-retry"),
  whiteIntervalSetup: document.getElementById("white-interval-setup"),
  lobbyStatus: document.getElementById("lobby-status"),
  lobbyOrderInterval: document.getElementById("lobby-order-interval"),
  roleTag: document.getElementById("role-tag"),
  boardGrid: document.getElementById("board-grid"),
  boardWrap: document.getElementById("board-wrap"),
  status: document.getElementById("status"),
  orderSection: document.getElementById("order-section"),
  orderInput: document.getElementById("order-input"),
  charCount: document.getElementById("char-count"),
  submitOrder: document.getElementById("submit-order"),
  reasoningSection: document.getElementById("reasoning-section"),
  reasoningText: document.getElementById("reasoning-text"),
  orderIntervalRow: document.getElementById("order-interval-row"),
  orderInterval: document.getElementById("order-interval"),
  gameOverSection: document.getElementById("game-over-section"),
  gameOverTitle: document.getElementById("game-over-title"),
  gameOverDetail: document.getElementById("game-over-detail"),
  returnSetup: document.getElementById("return-setup"),
  gameSettings: document.getElementById("game-settings"),
  concede: document.getElementById("concede"),
};

const FILES = "abcdefgh";
const PIECE_COLOR_NAMES = { w: "white", b: "black" };

/** Role is fixed by URL path — each tab gets its own side (/white or /black). */
function sideFromPath() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  if (path === "/white") return "white";
  if (path === "/black") return "black";
  return null;
}

function isLandingPage() {
  return sideFromPath() === null;
}

function pieceImageSrc(color, type) {
  const colorName = PIECE_COLOR_NAMES[color] || color;
  return `/static/images/pieces/${colorName}-${type}.png`;
}

function isMyTurn(state) {
  return state.turn === playerColor;
}

function isSeatedInLobby(state) {
  const lobby = state.lobby || {};
  if (!playerColor) return false;
  if (playerColor === "white") return lobby.white_taken && Boolean(playerToken);
  if (playerColor === "black") return lobby.black_taken && Boolean(playerToken);
  return false;
}

function updateLandingLobby(state) {
  const lobby = state.lobby || {};
  if (lobby.match_winding_down) {
    els.lobbyStatus.textContent =
      "A finished game is still being reviewed — wait for both commanders to return to setup.";
    return;
  }
  const parts = [];
  if (lobby.white_taken) parts.push("White connected");
  if (lobby.black_taken) parts.push("Black connected");
  if (parts.length === 0) {
    els.lobbyStatus.textContent = "Nobody connected yet.";
  } else if (lobby.ready) {
    els.lobbyStatus.textContent = "Both players connected — game starting…";
  } else {
    els.lobbyStatus.textContent = `${parts.join(" · ")} — waiting for the other player…`;
  }
}

function showGame() {
  stopLobbyPolling();
  els.teamScreen.classList.add("hidden");
  els.gameScreen.classList.remove("hidden");
  updateRoleTag();
}

function updateRoleTag(state) {
  const color = state?.your_color || playerColor;
  if (!color) return;
  const label = color === "white" ? "White" : "Black";
  const path = window.location.pathname;
  const pathSide = sideFromPath();
  let text = `You are ${label}`;
  if (pathSide && pathSide !== color) {
    text += ` — open /${color} for this seat (you are on ${path})`;
  } else if (pathSide) {
    text += ` (${path})`;
  }
  els.roleTag.textContent = text;
}

function showLanding() {
  stopPolling();
  playerColor = null;
  playerToken = null;
  els.gameScreen.classList.add("hidden");
  els.teamScreen.classList.remove("hidden");
  els.landingPicker.classList.remove("hidden");
  els.sideJoinPanel.classList.add("hidden");
  refreshLobbyFromServer();
  startLobbyPolling();
}

function showSideJoinPanel(color, { message = "", showRetry = false } = {}) {
  stopPolling();
  playerColor = color;
  playerToken = loadStoredToken(color);
  els.gameScreen.classList.add("hidden");
  els.teamScreen.classList.remove("hidden");
  els.landingPicker.classList.add("hidden");
  els.sideJoinPanel.classList.remove("hidden");
  els.sideRoleLabel.textContent =
    color === "white" ? "White player window" : "Black player window";
  els.sideJoinStatus.textContent = message;
  els.sideRetry.classList.toggle("hidden", !showRetry);
  els.whiteIntervalSetup.classList.toggle("hidden", color !== "white");
}

function gameOverCopy(state) {
  const reason = state.end_reason;
  const won = state.winner === playerColor;
  const lost = state.winner && state.winner !== playerColor && state.winner !== "draw";
  const draw = state.winner === "draw";

  if (draw) {
    return {
      kind: "draw",
      title: "Draw",
      detail: state.status_message || "The game is a draw.",
    };
  }
  if (won) {
    const detail =
      reason === "checkmate"
        ? "Checkmate."
        : reason === "concession"
          ? "Your opponent conceded."
          : state.status_message || "";
    return { kind: "win", title: "You won!", detail };
  }
  if (lost) {
    if (reason === "concession") {
      return { kind: "loss", title: "You conceded", detail: "Your opponent wins." };
    }
    if (reason === "checkmate") {
      return { kind: "loss", title: "Checkmate!", detail: "You lost." };
    }
    return {
      kind: "loss",
      title: "You lost",
      detail: state.status_message || "",
    };
  }
  return {
    kind: "neutral",
    title: "Game over",
    detail: state.status_message || "",
  };
}

function renderGameOverPanel(state) {
  const over = state.game_over || state.phase === "game_over";
  els.gameOverSection.classList.toggle("hidden", !over);
  els.gameSettings.classList.toggle("hidden", over);

  if (!over) {
    els.gameOverSection.classList.remove("win", "loss", "draw");
    return;
  }

  const copy = gameOverCopy(state);
  els.gameOverTitle.textContent = copy.title;
  els.gameOverDetail.textContent = copy.detail;
  els.gameOverSection.classList.toggle("win", copy.kind === "win");
  els.gameOverSection.classList.toggle("loss", copy.kind === "loss");
  els.gameOverSection.classList.toggle("draw", copy.kind === "draw");
}

function finishBusy() {
  busy = false;
  if (lastState) renderState(lastState);
}

function renderBoard(state) {
  lastState = state;
  els.boardGrid.innerHTML = "";

  if (state.phase === "lobby") {
    els.boardWrap.classList.remove("select-mode", "king-move-mode", "busy");
    return;
  }

  const myTurn = isMyTurn(state);
  const selectMode =
    state.phase === "select_piece" &&
    myTurn &&
    !state.game_over &&
    state.phase !== "game_over";
  const kingMoveMode =
    state.phase === "resolve_move" &&
    myTurn &&
    state.legal_moves?.length > 0 &&
    state.selectable_pieces?.find((p) => p.agent_id === state.selected_agent_id)
      ?.manual_move;

  els.boardWrap.classList.toggle("select-mode", selectMode);
  els.boardWrap.classList.toggle("king-move-mode", kingMoveMode);
  els.boardWrap.classList.toggle("busy", busy);

  const grid = state.board_grid || [];
  grid.forEach((row, rowIdx) => {
    const rank = 8 - rowIdx;
    const rankLabel = document.createElement("div");
    rankLabel.className = "rank-label";
    rankLabel.textContent = String(rank);
    els.boardGrid.appendChild(rankLabel);

    row.forEach((sq) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "square";
      cell.dataset.x = sq.x;
      cell.dataset.y = sq.y;
      cell.dataset.label = sq.label;

      if (sq.light) cell.classList.add("light");
      else cell.classList.add("dark");
      if (sq.selected) cell.classList.add("selected");
      if (sq.selectable) cell.classList.add("selectable");
      if (sq.is_target) cell.classList.add("target");
      if (sq.is_king && sq.piece && sq.piece === sq.piece.toUpperCase()) {
        cell.classList.add("king");
      }

      if (sq.piece_type && sq.piece_color) {
        const icon = document.createElement("img");
        icon.className = "piece-img";
        icon.src = pieceImageSrc(sq.piece_color, sq.piece_type);
        icon.alt = `${sq.piece_color === "w" ? "white" : "black"} ${sq.piece_type}`;
        cell.appendChild(icon);
      }

      if (!busy && myTurn) {
        cell.addEventListener("click", () => onSquareClick(sq));
      } else {
        cell.disabled = true;
      }

      els.boardGrid.appendChild(cell);
    });
  });

  const corner = document.createElement("div");
  corner.className = "rank-label";
  els.boardGrid.appendChild(corner);
  for (const f of FILES) {
    const fileLabel = document.createElement("div");
    fileLabel.className = "file-label";
    fileLabel.textContent = f;
    els.boardGrid.appendChild(fileLabel);
  }
}

function renderState(state) {
  if (state.your_color) {
    playerColor = state.your_color;
  }
  updateRoleTag(state);
  renderBoard(state);

  if (state.phase === "lobby") {
    els.status.textContent = state.status_message || "Waiting for the other player…";
    renderGameOverPanel(state);
    return;
  }

  let status = busy ? "Thinking…" : state.status_message || "";
  if (!busy && state.check && state.turn === playerColor && !state.game_over) {
    status = status ? `${status} You are in check.` : "You are in check.";
  }
  els.status.textContent = status;

  const showOrder =
    state.phase === "needs_order" &&
    state.needs_order_from === playerColor &&
    !state.game_over;
  els.orderSection.classList.toggle("hidden", !showOrder);

  const showReasoning = Boolean(state.last_reasoning) && !state.game_over;
  els.reasoningSection.classList.toggle("hidden", !showReasoning);
  els.reasoningText.textContent = state.last_reasoning || "";

  const canEditInterval =
    playerColor === "white" &&
    !state.settings?.order_interval_locked &&
    !state.game_over;
  els.orderIntervalRow.classList.toggle("hidden", !canEditInterval);
  if (state.settings?.order_interval) {
    els.orderInterval.value = state.settings.order_interval;
  }

  renderGameOverPanel(state);
}

async function fetchState() {
  return api("/api/state");
}

async function refresh() {
  const state = await fetchState();
  renderState(state);
  return state;
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (busy || !playerColor) return;
    try {
      const state = await fetchState();
      renderState(state);
      if (state.phase === "lobby" && !isSeatedInLobby(state) && !state.match_winding_down) {
        clearPlayerToken(playerColor);
        stopPolling();
        if (isLandingPage()) {
          showLanding();
        } else {
          window.location.replace("/");
        }
      }
    } catch {
      /* ignore transient poll errors */
    }
  }, POLL_MS);
}

function startLobbyPolling() {
  stopLobbyPolling();
  lobbyPollTimer = setInterval(async () => {
    if (playerColor) return;
    try {
      const state = await api("/api/state");
      if (isLandingPage()) updateLandingLobby(state);
    } catch {
      /* ignore transient poll errors */
    }
  }, POLL_MS);
}

function stopLobbyPolling() {
  if (lobbyPollTimer) {
    clearInterval(lobbyPollTimer);
    lobbyPollTimer = null;
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function joinTeam(color) {
  playerColor = color;
  playerToken = loadStoredToken(color);
  const body = { color };
  const stored = loadStoredToken(color);
  if (stored) {
    body.player_token = stored;
  }
  if (color === "white") {
    body.order_interval =
      Number(els.lobbyOrderInterval.value) ||
      Number(els.orderInterval.value) ||
      5;
  }

  if (!isLandingPage()) {
    showSideJoinPanel(color, { message: "Connecting…" });
  }

  try {
    const state = await api("/api/join", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (state.player_token) {
      savePlayerToken(color, state.player_token);
    }
    showGame();
    renderState(state);
    startPolling();
  } catch (e) {
    clearPlayerToken(color);
    playerColor = color;
    if (isLandingPage()) {
      els.lobbyStatus.textContent = e.message;
    } else {
      showSideJoinPanel(color, { message: e.message, showRetry: true });
    }
  }
}

async function onSquareClick(sq) {
  if (busy || !lastState || !isMyTurn(lastState)) return;

  const state = lastState;

  if (state.phase === "resolve_move" && sq.is_target) {
    const move = state.legal_moves.find(
      (m) => m.to_x === sq.x && m.to_y === sq.y
    );
    if (!move) return;
    busy = true;
    renderState({ ...state, status_message: "Moving king…" });
    try {
      const result = await api("/api/move/manual", {
        method: "POST",
        body: JSON.stringify({ uci: move.uci }),
      });
      lastState = result.state || result;
      renderState(lastState);
    } catch (e) {
      alert(e.message);
      await refresh();
    } finally {
      finishBusy();
    }
    return;
  }

  if (state.phase === "select_piece" && sq.selectable && sq.agent_id) {
    busy = true;
    renderState({
      ...state,
      status_message: `${sq.piece_type} is deciding…`,
    });
    try {
      const result = await api("/api/play-piece", {
        method: "POST",
        body: JSON.stringify({ agent_id: sq.agent_id }),
      });
      lastState = result.state || result;
      renderState(lastState);
    } catch (e) {
      alert(e.message);
      await refresh();
    } finally {
      finishBusy();
    }
  }
}

async function submitOrder() {
  const text = els.orderInput.value.trim();
  if (!text) return;
  els.submitOrder.disabled = true;
  try {
    const state = await api("/api/order", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    els.orderInput.value = "";
    updateCharCount();
    renderState(state);
  } catch (e) {
    alert(e.message);
  } finally {
    els.submitOrder.disabled = false;
  }
}

async function updateOrderInterval() {
  if (playerColor !== "white") return;
  const interval = Number(els.orderInterval.value);
  if (!interval || interval < 1) return;
  try {
    const state = await api("/api/settings/order-interval", {
      method: "POST",
      body: JSON.stringify({ order_interval: interval }),
    });
    renderState(state);
  } catch (e) {
    alert(e.message);
  }
}

async function concedeGame() {
  if (
    !confirm(
      "Concede this match? Your opponent wins and both players can review the board before returning to setup."
    )
  ) {
    return;
  }
  try {
    const state = await api("/api/concede", { method: "POST", body: "{}" });
    lastState = state;
    renderState(state);
  } catch (e) {
    alert(e.message);
  }
}

async function returnToSetup() {
  stopPolling();
  const side = sideFromPath();
  try {
    await api("/api/dismiss", { method: "POST", body: "{}" });
  } catch {
    /* lobby may already be cleared by the other player */
  }
  if (side) {
    clearPlayerToken(side);
  }
  playerColor = null;
  playerToken = null;
  window.location.replace("/");
}

function updateCharCount() {
  const n = els.orderInput.value.length;
  els.charCount.textContent = `${n}/140`;
}

async function init() {
  updateCharCount();
  const side = sideFromPath();
  if (side) {
    await joinTeam(side);
  } else {
    showLanding();
  }
}

els.sideRetry.addEventListener("click", () => {
  const side = sideFromPath();
  if (side) joinTeam(side);
});
els.orderInput.addEventListener("input", updateCharCount);
els.submitOrder.addEventListener("click", () => submitOrder());
els.concede.addEventListener("click", () => concedeGame());
els.returnSetup.addEventListener("click", () => returnToSetup());
els.orderInterval.addEventListener("change", () => updateOrderInterval());

init();

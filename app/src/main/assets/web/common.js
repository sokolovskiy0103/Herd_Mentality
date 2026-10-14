// Shared helpers for host and player pages.
const $ = (sel, root = document) => root.querySelector(sel);

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const LEVELS = { light: 'Легкий', spicy: 'Пікантний', hot: '18+', custom: 'Своє' };

function cow(pink = false, cls = 'cow') {
  const face = pink ? '#ff8fb5' : '#ffffff';
  const spot = pink ? '#c23b6e' : '#2b1b3d';
  return `<svg class="${cls}" viewBox="20 18 68 66" aria-hidden="true">
    <path fill="#fff4d6" d="M36,34 C30,30 29,24 32,21 C34,26 38,29 42,30 Z M72,34 C78,30 79,24 76,21 C74,26 70,29 66,30 Z"/>
    <path fill="${face}" d="M30,42 C22,40 19,46 24,49 C28,51 33,48 35,46 Z M78,42 C86,40 89,46 84,49 C80,51 75,48 73,46 Z M54,28 C68,28 76,38 76,52 C76,66 70,80 54,80 C38,80 32,66 32,52 C32,38 40,28 54,28 Z"/>
    <path fill="${spot}" d="M38,40 C42,34 50,36 48,42 C47,47 40,48 38,44 Z M66,34 C72,36 74,42 70,45 C67,47 63,42 64,38 Z"/>
    <circle fill="#2b1b3d" cx="45" cy="52" r="3"/><circle fill="#2b1b3d" cx="63" cy="52" r="3"/>
    <path fill="#ffb3cc" d="M54,60 C64,60 69,64 69,70 C69,76 63,80 54,80 C45,80 39,76 39,70 C39,64 44,60 54,60 Z"/>
    <circle fill="#c23b6e" cx="48" cy="69" r="2"/><circle fill="#c23b6e" cx="60" cy="69" r="2"/></svg>`;
}

/** WebSocket with automatic reconnect. onOpen fires on every (re)connect. */
function connect(path, { onMessage, onStatus, onOpen }) {
  let ws = null, tries = 0;
  const url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + path;
  function open() {
    ws = new WebSocket(url);
    ws.onopen = () => { tries = 0; onStatus && onStatus(true); onOpen && onOpen(); };
    ws.onmessage = e => { try { onMessage(JSON.parse(e.data)); } catch (err) { console.error(err); } };
    ws.onclose = () => { onStatus && onStatus(false); setTimeout(open, Math.min(4000, 400 * ++tries)); };
    ws.onerror = () => { try { ws.close(); } catch (_) {} };
  }
  open();
  // reconnect promptly when a phone wakes up
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && ws && ws.readyState > 1) open();
  });
  return {
    send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); },
  };
}

/** Re-render a container without losing what the user is typing in an input with an id. */
function renderKeepingInput(container, html) {
  const a = document.activeElement;
  const saved = {};
  container.querySelectorAll('input[id]').forEach(i => { saved[i.id] = i.value; });
  const focusId = a && a.id && a.tagName === 'INPUT' ? a.id : null;
  const sel = focusId ? [a.selectionStart, a.selectionEnd] : null;
  container.innerHTML = html;
  for (const id in saved) {
    const el = document.getElementById(id);
    if (el && !el.dataset.fresh) el.value = saved[id];
  }
  if (focusId) {
    const el = document.getElementById(focusId);
    if (el) { el.focus(); try { el.setSelectionRange(sel[0], sel[1]); } catch (_) {} }
  }
}

function scoreboard(st, { kick = false } = {}) {
  const ps = [...st.players].sort((a, b) => b.score - a.score);
  const scored = new Set(st.result ? st.result.scored : []);
  return `<div class="card">${ps.map(p => `
    <div class="score">
      <span class="dot ${p.connected ? '' : 'off'}"></span>
      <span class="name">${esc(p.name)}${st.me && st.me.id === p.id ? ' <span class="muted small">(ти)</span>' : ''}</span>
      ${st.pinkCow === p.id ? cow(true) : ''}
      ${scored.has(p.id) && (st.phase === 'RESULTS' || st.phase === 'GAMEOVER') ? '<span class="small" style="color:var(--green)">+1</span>' : ''}
      <span class="pts">${p.score}</span>${cow(false)}
      ${kick ? `<button class="mini ghost" data-kick="${p.id}">✕</button>` : ''}
    </div>`).join('') || '<div class="muted">Поки нікого</div>'}
    <div class="muted small" style="margin-top:8px">Гра до ${st.target} ${cowWord(st.target)}. Рожева корова не дає перемогти.</div>
  </div>`;
}

function cowWord(n) {
  const a = n % 10, b = n % 100;
  if (a === 1 && b !== 11) return 'корови';
  return 'корів';
}

function groupsHtml(st, { selectable = false, selected = null } = {}) {
  if (!st.groups) return '';
  const r = st.result;
  return st.groups.map((g, i) => {
    const win = r && r.majorityGroup === i;
    const isTarget = selectable && selected && !g.members.some(m => m.id === selected);
    return `<div class="group ${win ? 'win' : ''} ${isTarget ? 'target' : ''}" data-group="${i}">
      <div class="head">
        <span class="label">${esc(g.label)}</span>
        <span class="count">${g.members.length} ${win ? cow(false) : ''}</span>
      </div>
      <div>${g.members.map(m => `
        <span class="member ${st.me && st.me.id === m.id ? 'me' : ''} ${selected === m.id ? 'sel' : ''}" ${selectable ? `data-pid="${m.id}"` : ''}>
          <span>${esc(m.text)}</span><span class="who">${esc(m.name)}</span>
        </span>`).join('')}
      </div>
    </div>`;
  }).join('');
}

function resultLine(st) {
  const r = st.result;
  if (!r) return '';
  const name = id => esc((st.players.find(p => p.id === id) || {}).name || '?');
  const parts = [];
  if (r.majorityGroup >= 0) parts.push(`Стадо: ${r.scored.map(name).join(', ')} отримують по корові.`);
  else if (r.tie) parts.push('Нічия між найбільшими групами — ніхто не отримує корову.');
  else parts.push('Усі відповіли по-різному — стада немає.');
  if (r.pinkTo) parts.push(`Рожеву корову отримує ${name(r.pinkTo)}.`);
  return parts.join(' ');
}

// Host page: runs inside the app's WebView on the host phone.
(function () {
  const token = location.hash.slice(1);
  const app = $('#app'), bar = $('#bar'), barInner = $('#barInner');
  $('#logoCow').innerHTML = cow(false);

  let st = null;
  let selected = null;     // pid picked for moving during judging
  let urlIdx = 0;
  let armed = null;        // two-tap confirmation
  let showCustom = false;

  const sock = connect('/ws?host=' + encodeURIComponent(token), {
    onOpen() {
      const pid = localStorage.getItem('herd.host.pid');
      if (pid) sock.send({ t: 'resume', pid });
    },
    onStatus(ok) { $('#conn').innerHTML = `<span class="dot ${ok ? '' : 'off'}"></span>`; },
    onMessage(m) {
      if (m.t === 'unknown') localStorage.removeItem('herd.host.pid');
      if (m.t !== 'state') return;
      if (m.me) localStorage.setItem('herd.host.pid', m.me.id);
      if (st && (st.phase !== m.phase || st.round !== m.round)) { selected = null; showCustom = false; }
      st = m;
      render();
    },
  });

  // ---------- views ----------

  function aiPill(ai) {
    if (!ai) return '';
    return {
      READY: `🧠 Gemma`,
      DOWNLOADING: `⬇ ${Math.round(ai.progress * 100)}%`,
      LOADING: `🧠 завантаження…`,
      ERROR: `⚠ ШІ`,
      ABSENT: `без ШІ`,
    }[ai.state] || '';
  }

  function aiCard(ai) {
    let body = '';
    switch (ai.state) {
      case 'ABSENT':
        body = `<p class="muted small">Gemma 4 E2B прямо на цьому телефоні групує схожі відповіді: «тачка» = «машина». Розмір ≈2.6 ГБ, качається один раз — краще по Wi-Fi. Без неї працює простий автоматичний збіг, а спірне вирішуєш ти.</p>
          <button class="soft" data-act="downloadModel">Завантажити Gemma</button>`;
        break;
      case 'DOWNLOADING':
        body = `<div class="bar"><i style="width:${(ai.progress * 100).toFixed(1)}%"></i></div>
          <p class="muted small">${esc(ai.message)}. Можна грати вже зараз — модель підключиться сама.</p>
          <button class="mini ghost" data-act="deleteModel" data-confirm="cancelDl">${armed === 'cancelDl' ? 'Точно скасувати?' : 'Скасувати'}</button>`;
        break;
      case 'LOADING':
        body = `<p><span class="spinner"></span> <span class="muted">${esc(ai.message)}</span></p>`;
        break;
      case 'READY':
        body = `<p class="small">Готова, працює на ${esc(ai.backend)}.${ai.lastMillis ? ` Останнє судження: ${(ai.lastMillis / 1000).toFixed(1)} с.` : ''}</p>
          <button class="mini ghost" data-act="deleteModel" data-confirm="delModel">${armed === 'delModel' ? 'Точно видалити?' : 'Видалити модель'}</button>`;
        break;
      case 'ERROR':
        body = `<p class="small" style="color:var(--pink2)">${esc(ai.message)}</p>
          <p class="muted small">Гра працює й без моделі.</p>
          <button class="soft" data-act="downloadModel">Спробувати ще раз</button>`;
        break;
    }
    return `<div class="card"><h2>🧠 Суддя Gemma</h2>${body}</div>`;
  }

  function qrCard() {
    const urls = st.urls || [];
    if (!urls.length) {
      return `<div class="card center"><h2>Немає мережі</h2>
        <p class="muted">Підключись до Wi-Fi або увімкни точку доступу на цьому телефоні — QR-код з'явиться сам.</p></div>`;
    }
    if (urlIdx >= urls.length) urlIdx = 0;
    const u = urls[urlIdx];
    return `<div class="card center stack">
      <img class="qr" src="/qr.svg?t=${encodeURIComponent(u.url)}" alt="QR">
      <div class="url">${esc(u.url)}</div>
      <div class="muted small">${u.hotspot ? 'Гравці підключаються до твоєї точки доступу й сканують код.' : 'Гравці мають бути в тій самій Wi-Fi і сканують код камерою.'}</div>
      ${urls.length > 1 ? `<button class="mini ghost" data-act="nextUrl">Інша мережа (${urlIdx + 1}/${urls.length})</button>` : ''}
    </div>`;
  }

  function hostPlayer() {
    if (st.me) {
      return `<div class="row"><span class="grow">Ти граєш як <b>${esc(st.me.name)}</b></span>
        <button class="mini ghost" data-act="leave">Не граю</button></div>`;
    }
    const saved = esc(localStorage.getItem('herd.host.name') || '');
    return `<div class="row"><input id="hostName" class="grow" type="text" maxlength="20" placeholder="Твоє ім'я" value="${saved}" style="flex:1">
      <button data-act="hostJoin">Я теж граю</button></div>`;
  }

  function lobby() {
    const lv = new Set(st.levels);
    return `<div class="stack">
      ${qrCard()}
      <div class="card stack">
        <h2>Гравці (${st.players.length})</h2>
        <div class="chips">${st.players.map(p => `<span class="chip"><span class="dot ${p.connected ? '' : 'off'}"></span>${esc(p.name)}
          <button class="mini ghost" data-kick="${p.id}" style="min-height:24px;padding:0 6px">✕</button></span>`).join('') || '<span class="muted">Чекаємо, поки хтось відсканує QR…</span>'}</div>
        ${hostPlayer()}
      </div>
      <div class="card stack">
        <h2>Відвертість</h2>
        <div class="chips">${['light', 'spicy', 'hot'].map(l => `<button class="chip ${lv.has(l) ? 'on' : ''}" data-level="${l}">${LEVELS[l]}</button>`).join('')}</div>
        <button class="chip ${st.anonymous ? 'on' : ''}" data-act="anon" style="align-self:flex-start">${st.anonymous ? '🙈 Анонімні відповіді: так' : '👀 Анонімні відповіді: ні'}</button>
        <div class="muted small">${st.anonymous ? 'Під час розбору видно тільки тексти, без імен. Хто в стаді, все одно стане видно з рахунку.' : 'Під час розбору біля кожної відповіді видно, хто її написав.'}</div>
        <div class="row"><span class="grow">Гра до</span>
          <button class="mini soft" data-act="targetDown">−</button>
          <b style="min-width:2ch;text-align:center">${st.target}</b>
          <button class="mini soft" data-act="targetUp">+</button>
          <span>${cowWord(st.target)}</span></div>
      </div>
      ${aiCard(st.ai)}
    </div>`;
  }

  function customBox() {
    if (!showCustom) return `<button class="ghost" data-act="showCustom" style="width:100%">✍️ Своє питання</button>`;
    return `<div class="row"><input id="custom" type="text" maxlength="200" placeholder="Напиши своє питання" style="flex:1">
      <button data-act="custom">Задати</button></div>`;
  }

  function myAnswerBox() {
    if (!st.me) return '';
    const a = st.me.answer;
    return `<div class="card flat stack">
      ${a ? `<div><span class="muted small">Твоя відповідь:</span> <b>${esc(a)}</b></div>` : ''}
      <div class="row"><input id="ans-${st.round}-${esc(st.question).length}" type="text" maxlength="80" placeholder="${a ? 'Змінити' : 'Твоя відповідь'}" autocomplete="off" style="flex:1">
      <button data-act="answer">${a ? 'Змінити' : 'OK'}</button></div>
    </div>`;
  }

  function questionView() {
    return `<div class="stack">
      <div class="row"><span class="tag ${st.questionLevel}">${LEVELS[st.questionLevel] || ''}</span><span class="muted small">Раунд ${st.round}</span></div>
      <div class="question">${esc(st.question)}</div>
      <div class="chips">${st.players.map(p => `<span class="chip ${p.answered ? 'done' : ''}">${p.answered ? '✓' : '…'} ${esc(p.name)}</span>`).join('')}</div>
      ${myAnswerBox()}
      ${customBox()}
    </div>`;
  }

  function judgingView() {
    const src = { gemma: '🧠 згрупувала Gemma', fuzzy: '🔤 автоматичний збіг', manual: '✋ виправлено вручну' }[st.groupSource] || '';
    return `<div class="stack">
      <div class="question" style="font-size:20px">${esc(st.question)}</div>
      ${st.judging
        ? `<div class="card flat center"><span class="spinner"></span> ${st.ai && st.ai.state === 'READY' ? 'Gemma групує відповіді…' : 'Групую відповіді…'}</div>`
        : `<div class="muted small">${src}. ${selected ? '<b style="color:var(--yellow)">Тепер тапни групу, куди перенести.</b>' : 'Не згоден? Тапни відповідь, потім групу.'}</div>`}
      <div class="stack" id="groups">${groupsHtml(st, { selectable: !st.judging, selected })}</div>
      ${selected ? `<button class="ghost" data-act="newGroup" style="width:100%">＋ В окрему групу</button>` : ''}
    </div>`;
  }

  function resultsView() {
    return `<div class="stack">
      <div class="card flat">${resultLine(st)}</div>
      <div class="stack">${groupsHtml(st)}</div>
      <h2>Рахунок</h2>${scoreboard(st, { kick: true })}
      ${customBox()}
    </div>`;
  }

  function gameOverView() {
    const names = (st.winners || []).map(id => esc((st.players.find(p => p.id === id) || {}).name)).join(', ');
    return `<div class="stack">
      <div class="banner good pop">${cow(false)}Перемога: ${names}</div>
      ${st.pinkCow ? `<div class="card flat center">${cow(true)} Рожева корова: ${esc((st.players.find(p => p.id === st.pinkCow) || {}).name)}</div>` : ''}
      <h2>Рахунок</h2>${scoreboard(st)}
    </div>`;
  }

  function render() {
    if (!st) return;
    $('#ai').textContent = aiPill(st.ai);
    const reset = $('#resetBtn');
    reset.hidden = st.phase === 'LOBBY' || st.phase === 'GAMEOVER';
    reset.textContent = armed === 'reset' ? 'Скинути все?' : '↺ Нова гра';
    let html = '', buttons = '';
    switch (st.phase) {
      case 'LOBBY':
        html = lobby();
        buttons = `<button class="big" data-act="start" ${st.players.length < 2 ? 'disabled' : ''}>${st.players.length < 2 ? 'Потрібно хоча б 2 гравці' : 'Почати гру'}</button>`;
        break;
      case 'QUESTION':
        html = questionView();
        buttons = `<button class="soft" data-act="skip">Інше питання</button>
          <button data-act="reveal" ${st.answeredCount < 1 ? 'disabled' : ''}>Розкрити ${st.answeredCount}/${st.players.length}</button>`;
        break;
      case 'JUDGING':
        html = judgingView();
        buttons = `<button class="soft" data-act="regroup" ${st.judging ? 'disabled' : ''}>Перегрупувати</button>
          <button data-act="confirm" ${st.judging ? 'disabled' : ''}>Зарахувати</button>`;
        break;
      case 'RESULTS':
        html = resultsView();
        buttons = `<button class="big" data-act="next">Наступне питання</button>`;
        break;
      case 'GAMEOVER':
        html = gameOverView();
        buttons = `<button class="big" data-act="newGame">Нова гра</button>`;
        break;
    }
    renderKeepingInput(app, html);
    barInner.innerHTML = buttons;
    bar.hidden = !buttons;
  }

  // ---------- actions ----------

  function act(name, el) {
    if (el && el.dataset.confirm && armed !== el.dataset.confirm) {
      armed = el.dataset.confirm;
      render();
      setTimeout(() => { if (armed === el.dataset.confirm) { armed = null; render(); } }, 3000);
      return;
    }
    armed = null;
    switch (name) {
      case 'nextUrl': urlIdx++; render(); break;
      case 'anon': sock.send({ t: 'anonymous', on: !st.anonymous }); break;
      case 'targetUp': sock.send({ t: 'target', target: st.target + 1 }); break;
      case 'targetDown': sock.send({ t: 'target', target: st.target - 1 }); break;
      case 'hostJoin': {
        const name = ($('#hostName')?.value || '').trim();
        if (!name) { $('#hostName')?.focus(); return; }
        localStorage.setItem('herd.host.name', name);
        sock.send({ t: 'join', name, pid: localStorage.getItem('herd.host.pid') || '' });
        break;
      }
      case 'leave': sock.send({ t: 'leave' }); localStorage.removeItem('herd.host.pid'); break;
      case 'answer': {
        const input = app.querySelector('input[id^="ans-"]');
        const text = (input?.value || '').trim();
        if (!text) return;
        sock.send({ t: 'answer', text });
        input.value = ''; input.blur();
        break;
      }
      case 'showCustom': showCustom = true; render(); $('#custom')?.focus(); break;
      case 'custom': {
        const text = ($('#custom')?.value || '').trim();
        if (!text) return;
        showCustom = false;
        sock.send({ t: 'custom', text });
        break;
      }
      case 'newGroup': if (selected) { sock.send({ t: 'move', pid: selected, to: -1 }); selected = null; } break;
      default: sock.send({ t: name });
    }
  }

  document.addEventListener('click', e => {
    const kick = e.target.closest('[data-kick]');
    if (kick) {
      const key = 'kick' + kick.dataset.kick;
      if (armed !== key) { armed = key; kick.textContent = 'Точно?'; setTimeout(() => { if (armed === key) { armed = null; render(); } }, 3000); return; }
      armed = null; sock.send({ t: 'kick', pid: kick.dataset.kick }); return;
    }
    const lvl = e.target.closest('[data-level]');
    if (lvl) {
      const set = new Set(st.levels);
      set.has(lvl.dataset.level) ? set.delete(lvl.dataset.level) : set.add(lvl.dataset.level);
      if (set.size) sock.send({ t: 'levels', levels: [...set] });
      return;
    }
    const a = e.target.closest('[data-act]');
    if (a) { act(a.dataset.act, a); return; }
    if (st && st.phase === 'JUDGING' && !st.judging) {
      const m = e.target.closest('[data-pid]');
      if (m) { selected = selected === m.dataset.pid ? null : m.dataset.pid; render(); return; }
      const g = e.target.closest('[data-group]');
      if (g && selected) { sock.send({ t: 'move', pid: selected, to: +g.dataset.group }); selected = null; return; }
    }
  });

  app.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    if (e.target.id === 'hostName') act('hostJoin');
    else if (e.target.id === 'custom') act('custom');
    else if (e.target.id && e.target.id.startsWith('ans-')) act('answer');
  });
})();

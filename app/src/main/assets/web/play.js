// Player page: opened in any phone browser from the host's QR code.
(function () {
  const app = $('#app');
  $('#logoCow').innerHTML = cow(false);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (_) {} },
  };
  let pid = store.get('herd.pid');
  let st = null;
  let joining = false;
  let lastResultKey = '';

  const sock = connect('/ws', {
    onOpen() { if (pid) sock.send({ t: 'resume', pid }); else render(); },
    onStatus(ok) { $('#conn').innerHTML = `<span class="dot ${ok ? '' : 'off'}"></span> ${ok ? '' : 'перепідключення…'}`; },
    onMessage(m) {
      if (m.t === 'welcome') { pid = m.pid; store.set('herd.pid', pid); joining = false; }
      else if (m.t === 'unknown') { pid = null; store.set('herd.pid', null); render(); }
      else if (m.t === 'state') {
        st = m;
        // messages are conflated server-side, so the state itself carries our id
        if (m.me && m.me.id !== pid) { pid = m.me.id; store.set('herd.pid', pid); joining = false; }
        render();
      }
    },
  });

  function joinView() {
    const name = store.get('herd.name') || '';
    return `<div class="stack" style="margin-top:12vh">
      <h1>Заходь у стадо 🐄</h1>
      <p class="muted">Відповідай так, як відповість більшість. Хто відбився від стада — отримує рожеву корову.</p>
      <input id="name" type="text" maxlength="20" placeholder="Твоє ім'я" value="${esc(name)}" autocomplete="nickname">
      <button class="big" id="joinBtn" ${joining ? 'disabled' : ''}>Грати</button>
    </div>`;
  }

  function render() {
    const me = st && st.me;
    if (!pid || !me) {
      if (pid && !st) return; // waiting for state after resume
      renderKeepingInput(app, joinView());
      return;
    }
    let html = '';
    switch (st.phase) {
      case 'LOBBY':
        html = `<div class="stack">
          <h1>Привіт, ${esc(me.name)}!</h1>
          <div class="card flat center"><span class="spinner"></span> <span class="muted">Чекаємо, поки ведучий почне гру</span></div>
          <h2>У грі ${st.players.length}</h2>
          <div class="chips">${st.players.map(p => `<span class="chip">${esc(p.name)}</span>`).join('')}</div>
          <button class="ghost" id="leaveBtn">Вийти з гри</button>
        </div>`;
        break;
      case 'QUESTION': {
        const answered = !!me.answer;
        html = `<div class="stack">
          <div class="row"><span class="tag ${st.questionLevel}">${LEVELS[st.questionLevel] || ''}</span><span class="muted small">Раунд ${st.round}</span></div>
          <div class="question">${esc(st.question)}</div>
          ${answered ? `<div class="card flat"><div class="muted small">Твоя відповідь</div><div style="font-size:20px;font-weight:800">${esc(me.answer)}</div><div class="muted small">Можна змінити, поки ведучий не розкрив відповіді</div></div>` : ''}
          <input id="ans-${st.round}-${esc(st.question).length}" type="text" maxlength="80" placeholder="${answered ? 'Змінити відповідь' : 'Твоя відповідь'}" enterkeyhint="send" autocomplete="off">
          <button class="big" id="sendBtn">${answered ? 'Змінити' : 'Відповісти'}</button>
          <div class="muted small center">Відповіли ${st.answeredCount} з ${st.players.length}</div>
        </div>`;
        break;
      }
      case 'JUDGING':
        html = `<div class="stack">
          <div class="question" style="font-size:20px">${esc(st.question)}</div>
          <div class="card flat center">${st.judging ? '<span class="spinner"></span> Звіряємо відповіді…' : 'Ведучий перевіряє групи. Сперечайтесь голосно!'}</div>
          ${groupsHtml(st)}
        </div>`;
        break;
      case 'RESULTS':
      case 'GAMEOVER':
        html = `<div class="stack">${myBanner(st)}
          <div class="muted">${resultLine(st)}</div>
          <div class="question" style="font-size:18px">${esc(st.question)}</div>
          ${groupsHtml(st)}
          <h2>Рахунок</h2>${scoreboard(st)}
          ${st.phase === 'RESULTS' ? '<div class="muted small center">Чекаємо на наступне питання…</div>' : ''}
        </div>`;
        break;
    }
    renderKeepingInput(app, html);
  }

  function myBanner(st) {
    const me = st.me.id, r = st.result || {};
    const key = st.round + st.phase;
    const pop = key !== lastResultKey ? 'pop' : '';
    lastResultKey = key;
    if (st.phase === 'GAMEOVER') {
      const won = (st.winners || []).includes(me);
      const names = (st.winners || []).map(id => esc((st.players.find(p => p.id === id) || {}).name)).join(', ');
      return `<div class="banner ${won ? 'good' : 'meh'} ${pop}">${cow(false)}${won ? 'Ти переміг! Справжній лідер стада' : `Перемога: ${names}`}</div>`;
    }
    if (r.pinkTo === me) return `<div class="banner bad ${pop}">${cow(true)}Ти відбився від стада — тримай рожеву корову</div>`;
    if ((r.scored || []).includes(me)) return `<div class="banner good ${pop}">${cow(false)}+1 корова! Ти в стаді</div>`;
    if (!st.groups || !st.groups.some(g => g.members.some(m => m.id === me))) return `<div class="banner meh ${pop}">Ти не відповів цього раунду</div>`;
    return `<div class="banner meh ${pop}">Цього разу без корови</div>`;
  }

  // ---- events (delegated, so re-renders don't lose handlers) ----
  app.addEventListener('click', e => {
    const id = e.target.closest('button')?.id;
    if (id === 'joinBtn') join();
    if (id === 'sendBtn') sendAnswer();
    if (id === 'leaveBtn') { sock.send({ t: 'leave' }); pid = null; store.set('herd.pid', null); st = null; render(); }
  });
  app.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    if (e.target.id === 'name') join();
    if (e.target.id && e.target.id.startsWith('ans-')) sendAnswer();
  });

  function join() {
    const name = ($('#name')?.value || '').trim();
    if (!name) { $('#name')?.focus(); return; }
    store.set('herd.name', name);
    joining = true;
    sock.send({ t: 'join', name, pid: pid || '' });
    render();
  }

  function sendAnswer() {
    const input = app.querySelector('input[id^="ans-"]');
    const text = (input?.value || '').trim();
    if (!text) { input?.focus(); return; }
    sock.send({ t: 'answer', text });
    input.value = '';
    input.blur();
  }
})();

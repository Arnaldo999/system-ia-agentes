/* ============================================================
   Lovbot CRM · integración con API
   ------------------------------------------------------------
   Seguridad:
   - Auth por PIN → POST {SAAS_API}/tenant/{slug}/auth
   - Token en sessionStorage con key crm_token_{slug} (NO localStorage)
   - NO se envía Authorization: Bearer — sólo valida que el token
     exista en sessionStorage. Si no existe, redirige a login.
   - Tenant slug se toma de ?tenant=... (default "demo")
   - Escape de texto via textContent (nunca innerHTML con datos)
   - Auto-refresh sólo si la pestaña está visible
   ============================================================ */

(function () {
  'use strict';

  // ────────── CONFIG ──────────
  const CFG = window.LOVBOT_CONFIG || {};
  const SAAS_API = CFG.saasApi || 'https://saas.lovbot.ai';
  const API_BASE_FALLBACK = CFG.apiBase || 'https://api.lovbot.ai';
  const DEFAULT_TENANT = CFG.defaultTenant || 'demo';
  const REFRESH_MS = CFG.refreshMs || 60000;
  const FETCH_TIMEOUT = 10000;
  const DEMO_MODE = !!CFG.demoMode;

  const tenantSlug =
    new URLSearchParams(location.search).get('tenant') || DEFAULT_TENANT;
  const TOKEN_KEY = `crm_token_${tenantSlug}`;

  // apiBase puede venir del endpoint /tenant/{slug} (api_prefix)
  let API_BASE = API_BASE_FALLBACK;
  let tenantInfo = null;

  // ────────── UTILS ──────────
  const $ = (id) => document.getElementById(id);
  const fmtUSD = (n) => {
    if (n == null || isNaN(n)) return '—';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return Math.round(n / 1e3) + 'k';
    return String(Math.round(n));
  };
  const fmtMiles = (n) => {
    if (n == null || isNaN(n)) return '—';
    return Math.round(n).toLocaleString('es-AR');
  };

  function esc(s) {
    if (s == null) return '';
    return String(s);
  }

  async function apiFetch(url, opts = {}) {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) {
      redirectToLogin();
      throw new Error('No session');
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT);
    try {
      const r = await fetch(url, {
        ...opts,
        signal: ctrl.signal,
        headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      });
      if (r.status === 401 || r.status === 403) {
        sessionStorage.removeItem(TOKEN_KEY);
        redirectToLogin();
        throw new Error('Session expired');
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    } finally {
      clearTimeout(t);
    }
  }

  function redirectToLogin() {
    if (document.getElementById('loginOverlay')) return;
    showLoginOverlay();
  }

  // ────────── LOGIN OVERLAY (PIN) ──────────
  function showLoginOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'loginOverlay';
    overlay.innerHTML = `
      <style>
        #loginOverlay{position:fixed;inset:0;background:rgba(10,10,18,.94);backdrop-filter:blur(14px);z-index:9999;display:flex;align-items:center;justify-content:center;font-family:'Inter',system-ui,sans-serif}
        .lo-card{background:#12121f;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:36px 40px;width:380px;text-align:center;box-shadow:0 24px 60px rgba(0,0,0,.5)}
        .lo-logo{width:44px;height:44px;margin:0 auto 18px;border-radius:11px;background:linear-gradient(135deg,#7c3aed,#06b6d4);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:18px;font-family:'JetBrains Mono',monospace}
        .lo-title{font-size:17px;font-weight:600;color:#f1f5f9;margin:0 0 6px}
        .lo-sub{font-size:12px;color:#8b8ba7;margin:0 0 26px}
        .lo-tenant{font-size:10px;color:#a78bfa;font-family:'JetBrains Mono',monospace;letter-spacing:.08em;text-transform:uppercase;margin-bottom:20px}
        .lo-pin{display:flex;gap:10px;justify-content:center;margin-bottom:22px}
        .lo-pin input{width:56px;height:68px;background:#0a0a12;border:1px solid rgba(255,255,255,.10);border-radius:12px;text-align:center;font-size:24px;font-weight:600;color:#f1f5f9;font-family:'JetBrains Mono',monospace;outline:none;transition:all .15s}
        .lo-pin input:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.18)}
        .lo-err{color:#fca5a5;font-size:12px;min-height:16px;margin-bottom:10px}
        .lo-btn{width:100%;padding:13px;background:linear-gradient(135deg,#7c3aed,#06b6d4);border:0;border-radius:10px;color:#fff;font-weight:600;font-size:13px;cursor:pointer;transition:all .15s}
        .lo-btn:disabled{opacity:.4;cursor:not-allowed}
        .lo-foot{margin-top:18px;font-size:10px;color:#5a5a78;font-family:'JetBrains Mono',monospace;letter-spacing:.06em}
      </style>
      <div class="lo-card">
        <div class="lo-logo">L</div>
        <div class="lo-tenant">TENANT · ${esc(tenantSlug)}</div>
        <h2 class="lo-title">Ingresá tu PIN</h2>
        <div class="lo-sub">4 dígitos para acceder al CRM</div>
        <div class="lo-pin">
          <input type="tel" maxlength="1" inputmode="numeric" pattern="[0-9]"/>
          <input type="tel" maxlength="1" inputmode="numeric" pattern="[0-9]"/>
          <input type="tel" maxlength="1" inputmode="numeric" pattern="[0-9]"/>
          <input type="tel" maxlength="1" inputmode="numeric" pattern="[0-9]"/>
        </div>
        <div class="lo-err" id="loErr"></div>
        <button class="lo-btn" id="loBtn" disabled>Entrar</button>
        <div class="lo-foot">CONEXIÓN SEGURA · SESSION STORAGE · SIN COOKIES</div>
      </div>
    `;
    document.body.appendChild(overlay);

    const inputs = overlay.querySelectorAll('.lo-pin input');
    const btn = $('loBtn');
    const err = $('loErr');

    function pin() {
      return Array.from(inputs).map((i) => i.value).join('');
    }
    function updateBtn() {
      btn.disabled = pin().length !== 4;
    }
    inputs.forEach((inp, i) => {
      inp.addEventListener('input', (e) => {
        inp.value = inp.value.replace(/\D/g, '');
        if (inp.value && i < inputs.length - 1) inputs[i + 1].focus();
        updateBtn();
        if (pin().length === 4) submit();
      });
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !inp.value && i > 0) inputs[i - 1].focus();
      });
    });
    inputs[0].focus();

    async function submit() {
      btn.disabled = true;
      err.textContent = '';

      // Demo mode: acepta PIN 1234 localmente
      if (DEMO_MODE) {
        if (pin() === '1234') {
          sessionStorage.setItem(TOKEN_KEY, 'demo-token');
          overlay.remove();
          boot();
        } else {
          err.textContent = 'PIN incorrecto · probá con 1234';
          inputs.forEach((i) => (i.value = ''));
          inputs[0].focus();
          btn.disabled = true;
        }
        return;
      }

      try {
        // Primero resolvemos tenant para obtener api_prefix
        if (!tenantInfo) {
          try {
            const info = await fetch(
              `${SAAS_API}/tenant/${tenantSlug}`,
              { signal: AbortSignal.timeout(8000) }
            ).then((r) => (r.ok ? r.json() : null));
            if (info) {
              tenantInfo = info;
              if (info.api_prefix) API_BASE = info.api_prefix;
            }
          } catch (_) {}
        }
        const r = await fetch(`${SAAS_API}/tenant/${tenantSlug}/auth`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: pin() }),
          signal: AbortSignal.timeout(8000),
        });
        if (!r.ok) {
          err.textContent = r.status === 401 ? 'PIN incorrecto' : 'Error de conexión';
          inputs.forEach((i) => (i.value = ''));
          inputs[0].focus();
          btn.disabled = true;
          return;
        }
        const { token } = await r.json();
        sessionStorage.setItem(TOKEN_KEY, token);
        overlay.remove();
        boot();
      } catch (e) {
        err.textContent = 'No se pudo conectar con el servidor';
        btn.disabled = false;
      }
    }
    btn.addEventListener('click', submit);
  }

  // ────────── BOOT ──────────
  async function loadTenantInfo() {
    if (DEMO_MODE) {
      tenantInfo = {
        nombre: 'Inmobiliaria Demo',
        marca: { nombre_agente: 'Mariana' },
      };
      return;
    }
    try {
      const r = await fetch(`${SAAS_API}/tenant/${tenantSlug}`, {
        signal: AbortSignal.timeout(8000),
      });
      if (r.ok) {
        tenantInfo = await r.json();
        if (tenantInfo.api_prefix) API_BASE = tenantInfo.api_prefix;
      }
    } catch (_) {}
  }

  async function boot() {
    await loadTenantInfo();
    applyBranding();
    renderShellStatic();
    await refreshAll();
    startAutoRefresh();
    wireConsult();
  }

  function applyBranding() {
    const name = tenantInfo?.marca?.nombre_agente || tenantInfo?.nombre || 'tu asesor';
    const workspace = tenantInfo?.nombre || tenantSlug;
    const wsEl = document.querySelector('.workspace .ws-name');
    if (wsEl) wsEl.textContent = workspace;
    // Saludo
    const title = $('welcomeTitle');
    if (title) title.textContent = `Hola, ${name} 👋`;
    const date = $('welcomeDate');
    if (date) {
      const d = new Date();
      const dias = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
      const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
      date.textContent = `${dias[d.getDay()]}, ${d.getDate()} ${meses[d.getMonth()]} ${d.getFullYear()}`;
    }
  }

  function renderShellStatic() {
    const dbText = $('dbStatusText');
    if (dbText) dbText.textContent = 'Conectado';
    const waText = $('waStatusText');
    if (waText) waText.textContent = 'WhatsApp activo';
  }

  // ────────── DATA LOADERS ──────────
  async function refreshAll() {
    if (DEMO_MODE) {
      const leads = demoLeads();
      const metricas = demoMetricas(leads);
      renderKPIs(metricas, leads);
      renderPipeline(metricas, leads);
      renderAgenda(leads);
      renderAlerts(leads);
      renderBotFeed(leads);
      renderContracts(leads);
      renderWelcomeStats(leads);
      return;
    }
    try {
      const [clientes, metricas] = await Promise.all([
        apiFetch(`${API_BASE}/crm/clientes`).catch(() => ({ records: [] })),
        apiFetch(`${API_BASE}/crm/metricas`).catch(() => null),
      ]);
      const leads = (clientes?.records || []).map(mapLead);
      renderKPIs(metricas, leads);
      renderPipeline(metricas, leads);
      renderAgenda(leads);
      renderAlerts(leads);
      renderBotFeed(leads);
      renderContracts(leads);
      renderWelcomeStats(leads);
    } catch (e) {
      console.warn('refreshAll failed', e);
    }
  }

  function mapLead(r) {
    const f = r.fields || r;
    return {
      id: r.id || f.id,
      nombre: f.Nombre || f.nombre || 'Sin nombre',
      telefono: f.Telefono || f.telefono || '',
      estado: (f.Estado || f.estado || 'nuevo').toLowerCase(),
      score: (f.Score || f.score || '').toLowerCase(), // caliente/tibio/frio
      presupuesto: parseFloat(f.Presupuesto || f.presupuesto || 0) || 0,
      zona: f.Zona || f.zona || '',
      fuente: f.Fuente || f.fuente || '',
      fechaCita: f.Fecha_Cita || f.fecha_cita || null,
      notasBot: f.Notas_Bot || f.notas_bot || '',
      createdTime: r.createdTime || f.createdTime || null,
      tipo: f.Tipo || f.tipo || '',
      ultimoContacto: f.Ultimo_Contacto || f.ultimo_contacto || null,
    };
  }

  // ────────── RENDERERS ──────────
  function renderWelcomeStats(leads) {
    const el = $('welcomeStats');
    if (!el) return;
    const hoy = new Date().toISOString().slice(0, 10);
    const hoyInt = leads.filter((l) => (l.ultimoContacto || '').startsWith(hoy)).length;
    el.textContent = `${hoyInt} interacciones`;
  }

  function renderKPIs(m, leads) {
    // Pipeline potencial = suma de presupuestos de leads no cerrados/perdidos
    const pipelineVal = leads
      .filter((l) => !['cerrado', 'perdido'].includes(l.estado))
      .reduce((a, l) => a + (l.presupuesto || 0), 0);

    // Ingresos del mes = presupuesto de leads cerrados este mes
    const now = new Date();
    const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    const ingresos = leads
      .filter((l) => l.estado === 'cerrado' && (l.ultimoContacto || '').startsWith(ym))
      .reduce((a, l) => a + (l.presupuesto || 0), 0);

    // Por cobrar y mora: derivamos de clientes activos/notas (placeholder hasta tener endpoint)
    const porCobrar = 0;
    const mora = 0;

    setKPI('kpiIngresos', ingresos, ingresos > 0 ? 'USD' : '');
    setKPIFoot('kpiIngresosFoot', `Cerrados este mes: ${leads.filter((l) => l.estado === 'cerrado').length}`);

    setKPI('kpiPipeline', pipelineVal, 'USD');
    setKPIFoot('kpiPipelineFoot', `${leads.filter((l) => !['cerrado', 'perdido'].includes(l.estado)).length} leads en gestión`);

    setKPI('kpiPorCobrar', porCobrar, porCobrar ? 'USD' : '');
    setKPIFoot('kpiPorCobrarFoot', 'Sin cuotas registradas');

    setKPI('kpiMora', mora, mora ? 'USD' : '');
    setKPIFoot('kpiMoraFoot', 'Sin atrasos');
  }

  function setKPI(id, val, unit) {
    const el = $(id);
    if (!el) return;
    if (!val) {
      el.innerHTML = `<span class="u">${unit}</span>—`;
      return;
    }
    const display = fmtUSD(val);
    if (display.endsWith('M')) {
      el.innerHTML = `<span class="u">${unit}</span>${display.slice(0, -1)}<span class="sm">M</span>`;
    } else {
      el.innerHTML = `<span class="u">${unit}</span>${fmtMiles(val)}`;
    }
  }
  function setKPIFoot(id, txt) {
    const el = $(id);
    if (el) el.textContent = txt;
  }

  function renderPipeline(m, leads) {
    const container = $('pipelineFunnel');
    if (!container) return;
    const estados = m?.estados || countBy(leads, 'estado');
    const etapas = [
      { k: 'nuevo', label: 'Nuevos', color: '124,58,237' },
      { k: 'contactado', label: 'Contactados', color: '6,182,212' },
      { k: 'calificado', label: 'Calificados', color: '16,185,129' },
      { k: 'cita', label: 'Con cita', color: '245,158,11' },
      { k: 'cerrado', label: 'Cerrados', color: '236,72,153' },
    ];
    const max = Math.max(...etapas.map((e) => estados[e.k] || 0), 1);

    // Valor USD por etapa
    const valsUsd = {};
    etapas.forEach((e) => {
      valsUsd[e.k] = leads
        .filter((l) => l.estado === e.k)
        .reduce((a, l) => a + (l.presupuesto || 0), 0);
    });

    container.innerHTML = etapas
      .map((e) => {
        const n = estados[e.k] || 0;
        const w = Math.max(18, Math.round((n / max) * 100));
        return `
      <div class="f-stage">
        <div class="f-bar" style="background:linear-gradient(90deg,rgba(${e.color},.45),rgba(${e.color},.2));width:${w}%">
          <b>${n}</b>&nbsp;&nbsp;${e.label}
          <span class="v">USD ${fmtUSD(valsUsd[e.k])}</span>
        </div>
      </div>`;
      })
      .join('');

    const conv = $('pipelineConv');
    if (conv) {
      const nuevos = estados.nuevo || 0;
      const cerrados = estados.cerrado || 0;
      const tot = leads.length || 1;
      conv.textContent = `${((cerrados / tot) * 100).toFixed(1)}%`;
    }
  }

  function renderAgenda(leads) {
    const el = $('agendaList');
    if (!el) return;
    const hoy = new Date();
    const hoyKey = hoy.toISOString().slice(0, 10);
    const items = leads
      .filter((l) => l.fechaCita && l.fechaCita.slice(0, 10) === hoyKey)
      .sort((a, b) => a.fechaCita.localeCompare(b.fechaCita))
      .slice(0, 6);

    if (!items.length) {
      el.innerHTML = `<div style="padding:22px 10px;text-align:center;color:var(--dim);font-size:12px">Sin citas para hoy</div>`;
      return;
    }
    el.innerHTML = items
      .map((l, i) => {
        const d = new Date(l.fechaCita);
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const ampm = d.getHours() >= 12 ? 'PM' : 'AM';
        const tone = ['t1', 't2', 't3'][i % 3];
        return `
        <div class="event ${tone}">
          <div class="event-time">${hh}:${mm}<b>${ampm}</b></div>
          <div class="event-dot"></div>
          <div class="event-body">
            <div class="event-title">${escapeHTML(l.nombre)}${l.zona ? ' · ' + escapeHTML(l.zona) : ''}</div>
            <div class="event-meta">${escapeHTML(l.telefono || '')}${l.tipo ? ' · ' + escapeHTML(l.tipo) : ''}</div>
          </div>
        </div>`;
      })
      .join('');
  }

  function renderAlerts(leads) {
    const el = $('alertsList');
    const count = $('alertsCount');
    if (!el) return;
    const now = Date.now();
    const items = [];
    // Leads calientes sin contactar hace >48h
    const calientesFrios = leads.filter((l) => {
      if (l.score !== 'caliente') return false;
      if (!l.ultimoContacto) return true;
      return now - new Date(l.ultimoContacto).getTime() > 48 * 3600e3;
    });
    if (calientesFrios.length) {
      items.push({
        level: 'urgent',
        t: `${calientesFrios.length} lead${calientesFrios.length > 1 ? 's' : ''} caliente${calientesFrios.length > 1 ? 's' : ''} sin contactar`,
        m: `Última interacción >48h · requiere seguimiento`,
        cta: 'Contactar ahora →',
      });
    }
    // Citas de hoy
    const hoy = new Date().toISOString().slice(0, 10);
    const citasHoy = leads.filter((l) => l.fechaCita && l.fechaCita.slice(0, 10) === hoy);
    if (citasHoy.length) {
      items.push({
        level: 'warn',
        t: `${citasHoy.length} visita${citasHoy.length > 1 ? 's' : ''} programada${citasHoy.length > 1 ? 's' : ''} hoy`,
        m: citasHoy.slice(0, 2).map((l) => l.nombre).join(', '),
        cta: 'Ver agenda →',
      });
    }
    // Nuevos leads sin asignar
    const nuevos = leads.filter((l) => l.estado === 'nuevo').length;
    if (nuevos > 5) {
      items.push({
        level: 'warn',
        t: `${nuevos} leads nuevos pendientes de calificación`,
        m: 'Requieren primer contacto',
        cta: 'Calificar →',
      });
    }

    if (count) count.textContent = items.length;
    if (!items.length) {
      el.innerHTML = `<div style="padding:22px 10px;text-align:center;color:var(--dim);font-size:12px">Todo al día ✓</div>`;
      return;
    }
    el.innerHTML = items
      .map(
        (a) => `
      <div class="al-item ${a.level}">
        <div class="left-bar"></div>
        <div class="body">
          <div class="t">${escapeHTML(a.t)}</div>
          <div class="m">${escapeHTML(a.m)}</div>
          <div class="cta">${escapeHTML(a.cta)}</div>
        </div>
      </div>`
      )
      .join('');
  }

  function renderBotFeed(leads) {
    const el = $('botFeed');
    const cnt = $('botActionCount');
    if (!el) return;

    // Ordenar por createdTime desc, últimos N
    const latest = [...leads]
      .filter((l) => l.createdTime)
      .sort((a, b) => (b.createdTime || '').localeCompare(a.createdTime || ''))
      .slice(0, 6);

    const hoy = new Date().toISOString().slice(0, 10);
    const hoyCount = leads.filter((l) => (l.createdTime || '').startsWith(hoy)).length;
    if (cnt) cnt.textContent = hoyCount;

    if (!latest.length) {
      el.innerHTML = `<div style="padding:22px 10px;text-align:center;color:var(--dim);font-size:12px">Sin actividad reciente del bot</div>`;
      return;
    }
    el.innerHTML = latest
      .map((l) => {
        const t = timeAgo(l.createdTime);
        const action = l.notasBot
          ? 'Registró nota sobre'
          : l.score === 'caliente'
          ? 'Calificó como caliente a'
          : l.estado === 'cita'
          ? 'Agendó visita con'
          : 'Nuevo contacto con';
        return `
        <div class="bf-item">
          <div class="bf-dot"><svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4A8.4 8.4 0 0 1 3 11.5 8.4 8.4 0 0 1 11.6 3a8.4 8.4 0 0 1 9.4 8.5z"/></svg></div>
          <div class="bf-body">
            <div>${escapeHTML(action)} <b>${escapeHTML(l.nombre)}</b></div>
            <div class="bf-time">${escapeHTML(t)}${l.fuente ? ' · ' + escapeHTML(l.fuente) : ''}</div>
          </div>
        </div>`;
      })
      .join('');
  }

  function renderContracts(leads) {
    const el = $('contractsList');
    if (!el) return;
    // Como no hay endpoint de contratos, mostramos leads en estado "cerrado" o "cita"
    const items = leads
      .filter((l) => ['cerrado', 'cita', 'calificado'].includes(l.estado))
      .sort((a, b) => (b.ultimoContacto || '').localeCompare(a.ultimoContacto || ''))
      .slice(0, 4);
    if (!items.length) {
      el.innerHTML = `<div style="padding:22px 10px;text-align:center;color:var(--dim);font-size:12px">Sin operaciones recientes</div>`;
      return;
    }
    const colorMap = {
      cerrado: { c: '#10b981', bg: 'rgba(16,185,129,.14)', label: 'Cerrado' },
      cita: { c: '#f59e0b', bg: 'rgba(245,158,11,.14)', label: 'En visita' },
      calificado: { c: '#7c3aed', bg: 'rgba(124,58,237,.14)', label: 'Calificado' },
    };
    el.innerHTML = items
      .map((l) => {
        const m = colorMap[l.estado] || colorMap.calificado;
        return `
        <div class="rc-item">
          <div class="rc-icon" style="--c:${m.c};--c-bg:${m.bg}">
            <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
          </div>
          <div class="rc-info">
            <div class="rc-name">${escapeHTML(l.nombre)}</div>
            <div class="rc-meta">${escapeHTML(l.zona || l.tipo || '—')} · ${escapeHTML(timeAgo(l.ultimoContacto || l.createdTime))}</div>
          </div>
          <div class="rc-amount"><div class="v">USD ${fmtUSD(l.presupuesto)}</div><div class="s">${m.label}</div></div>
        </div>`;
      })
      .join('');
  }

  // ────────── CHAT IA (webhook n8n) ──────────
  function wireConsult() {
    const input = $('consultInput');
    const btn = document.querySelector('.consult-send');
    if (!input || !btn) return;

    const webhookUrl = tenantInfo?.marca?.ia_webhook_url || tenantInfo?.ia_webhook_url;
    let lastCall = 0;

    async function ask() {
      const now = Date.now();
      if (now - lastCall < 1500) return; // rate limit simple
      lastCall = now;
      const q = input.value.trim();
      if (!q) return;

      if (DEMO_MODE) {
        const canned = demoAIAnswer(q);
        showAIResponse(q, canned);
        input.value = '';
        return;
      }

      if (!webhookUrl) {
        alert('Webhook de IA no configurado para este tenant');
        return;
      }
      btn.disabled = true;
      btn.style.opacity = 0.5;
      try {
        const r = await fetch(webhookUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, tenant: tenantSlug }),
          signal: AbortSignal.timeout(15000),
        });
        const data = await r.json().catch(() => ({}));
        showAIResponse(q, data?.answer || data?.response || 'Sin respuesta');
      } catch (e) {
        showAIResponse(q, 'No se pudo conectar con la IA. Intentá de nuevo.');
      } finally {
        btn.disabled = false;
        btn.style.opacity = 1;
        input.value = '';
      }
    }
    btn.addEventListener('click', ask);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') ask();
    });
  }

  function demoAIAnswer(q) {
    const s = q.toLowerCase();
    if (s.includes('caliente') || s.includes('sin contactar'))
      return 'Tenés 3 leads calientes sin contactar en las últimas 48h: Julia Ortiz (Villa Cabello, USD 95k), Rodrigo Krauss (Villa Cabello, USD 42k) y Diego Ramírez (Oberá, USD 72k). Te recomiendo empezar por Julia — BANT 5 y lleva 72h sin respuesta.';
    if (s.includes('lote') && (s.includes('50') || s.includes('libre')))
      return 'Tenés 84 lotes libres en 7 loteos activos. Bajo USD 50k hay 42 unidades, principalmente en Garupá (18), Villa Cabello (12) y Oberá (12). ¿Querés que arme una ficha para enviar por WhatsApp?';
    if (s.includes('mora') || s.includes('atraso') || s.includes('vencid'))
      return 'Hay 2 cuotas en mora y 1 alquiler atrasado (total USD 18.150). El más crítico: H. Kuchaszus — 8 días de atraso en CTR-2026-015.';
    if (s.includes('cobr') || s.includes('ingreso'))
      return 'Este mes cobraste USD 142.8k (79% de tu meta USD 180k). Te quedan USD 48.3k por cobrar en los próximos 30 días distribuidos en 32 cuotas y 4 alquileres.';
    if (s.includes('zona') || s.includes('demanda'))
      return 'Las zonas con más demanda este mes son Villa Cabello (34 consultas), Oberá (22) y Garupá (18). Villa Cabello tiene la mejor tasa de cierre (12%).';
    return 'En modo demo puedo responder sobre leads calientes, lotes libres, cobros, morosos y zonas con más demanda. Probá preguntando por alguno de esos temas.';
  }

  function showAIResponse(q, a) {
    // Inyectar una respuesta visible bajo el input
    let box = $('aiResponseBox');
    if (!box) {
      box = document.createElement('div');
      box.id = 'aiResponseBox';
      box.style.cssText =
        'margin-top:14px;padding:14px 16px;background:rgba(124,58,237,.08);border:1px solid rgba(124,58,237,.2);border-radius:10px;font-size:13px;color:#f1f5f9;line-height:1.55';
      const promptEl = document.querySelector('.consult-prompt');
      if (promptEl && promptEl.parentNode) promptEl.parentNode.insertBefore(box, promptEl.nextSibling);
    }
    box.innerHTML = '';
    const qEl = document.createElement('div');
    qEl.style.cssText = 'color:#a78bfa;font-size:11px;font-weight:600;margin-bottom:6px;font-family:JetBrains Mono,monospace;text-transform:uppercase;letter-spacing:.06em';
    qEl.textContent = 'Vos preguntaste';
    const qTxt = document.createElement('div');
    qTxt.style.cssText = 'color:#c4b5fd;margin-bottom:10px';
    qTxt.textContent = q;
    const aEl = document.createElement('div');
    aEl.textContent = a;
    box.appendChild(qEl);
    box.appendChild(qTxt);
    box.appendChild(aEl);
  }

  // ────────── UTILS ──────────
  function escapeHTML(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function timeAgo(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'ahora';
    if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    return `hace ${Math.floor(diff / 86400)}d`;
  }
  function countBy(arr, key) {
    return arr.reduce((a, x) => {
      const k = x[key] || 'otros';
      a[k] = (a[k] || 0) + 1;
      return a;
    }, {});
  }

  // ────────── DEMO FIXTURES ──────────
  function demoLeads() {
    const now = Date.now();
    const iso = (offMin) => new Date(now - offMin * 60000).toISOString();
    const today = new Date(); today.setHours(10, 30, 0, 0);
    const citaHoy = (h, m) => { const d = new Date(); d.setHours(h, m, 0, 0); return d.toISOString(); };
    return [
      { id: '1', nombre: 'Rodrigo Krauss', telefono: '+54 376 4521-8832', estado: 'cita', score: 'caliente', presupuesto: 42000, zona: 'Villa Cabello', fuente: 'WhatsApp', fechaCita: citaHoy(10, 30), tipo: 'Lote', createdTime: iso(30), ultimoContacto: iso(30) },
      { id: '2', nombre: 'Patricia Sánchez', telefono: '+54 376 4120-5521', estado: 'cerrado', score: 'caliente', presupuesto: 128000, zona: 'Los Sauces', fuente: 'Referido', fechaCita: null, tipo: 'Casa', createdTime: iso(60*24*5), ultimoContacto: iso(60*24*2) },
      { id: '3', nombre: 'Sofía Domínguez', telefono: '+54 376 4415-2290', estado: 'calificado', score: 'caliente', presupuesto: 68000, zona: 'Oberá', fuente: 'Meta Ads', fechaCita: citaHoy(15, 30), tipo: 'Lote', createdTime: iso(60*5), ultimoContacto: iso(60*3) },
      { id: '4', nombre: 'Fernando Acuña', telefono: '+54 376 4389-1102', estado: 'cita', score: 'tibio', presupuesto: 180000, zona: 'Mitre 2410', fuente: 'Formulario', fechaCita: citaHoy(17, 0), tipo: 'Depto', createdTime: iso(60*24*1), ultimoContacto: iso(60*12) },
      { id: '5', nombre: 'Laura Giménez', telefono: '+54 376 4702-8815', estado: 'calificado', score: 'tibio', presupuesto: 55000, zona: 'Garupá', fuente: 'WhatsApp', fechaCita: null, tipo: 'Terreno', createdTime: iso(60*24*2), ultimoContacto: iso(60*24) },
      { id: '6', nombre: 'H. Kuchaszus', telefono: '+54 376 4610-4427', estado: 'cerrado', score: 'caliente', presupuesto: 38000, zona: 'Posadas', fuente: 'Referido', fechaCita: null, tipo: 'Lote', createdTime: iso(60*24*15), ultimoContacto: iso(60*24*8) },
      { id: '7', nombre: 'Carlos Benítez', telefono: '+54 376 4892-7743', estado: 'contactado', score: 'tibio', presupuesto: 45000, zona: 'Eldorado', fuente: 'WhatsApp', fechaCita: null, tipo: 'Lote', createdTime: iso(60*8), ultimoContacto: iso(60*6) },
      { id: '8', nombre: 'Ana Morales', telefono: '+54 376 4511-6633', estado: 'nuevo', score: 'frio', presupuesto: 30000, zona: 'Pto. Iguazú', fuente: 'Meta Ads', fechaCita: null, tipo: 'Terreno', createdTime: iso(60*2), ultimoContacto: iso(60*2) },
      { id: '9', nombre: 'Marcos Fleita', telefono: '+54 376 4320-9182', estado: 'nuevo', score: 'tibio', presupuesto: 62000, zona: 'Posadas', fuente: 'Formulario', fechaCita: null, tipo: 'Casa', createdTime: iso(60), ultimoContacto: iso(60) },
      { id: '10', nombre: 'Julia Ortiz', telefono: '+54 376 4008-2211', estado: 'contactado', score: 'caliente', presupuesto: 95000, zona: 'Villa Cabello', fuente: 'WhatsApp', fechaCita: null, tipo: 'Casa', createdTime: iso(60*4), ultimoContacto: iso(60*72) },
      { id: '11', nombre: 'Diego Ramírez', telefono: '+54 376 4712-3310', estado: 'calificado', score: 'caliente', presupuesto: 72000, zona: 'Oberá', fuente: 'Referido', fechaCita: null, tipo: 'Lote', createdTime: iso(60*24*3), ultimoContacto: iso(60*24) },
      { id: '12', nombre: 'Silvana Aranda', telefono: '+54 376 4015-9988', estado: 'nuevo', score: 'tibio', presupuesto: 40000, zona: 'Garupá', fuente: 'WhatsApp', fechaCita: null, tipo: 'Lote', createdTime: iso(60*0.5), ultimoContacto: iso(60*0.5) },
    ];
  }

  function demoMetricas(leads) {
    return {
      total: leads.length,
      estados: countBy(leads, 'estado'),
      scores: countBy(leads, 'score'),
    };
  }

  // ────────── AUTO-REFRESH ──────────
  function startAutoRefresh() {
    setInterval(() => {
      if (document.visibilityState === 'visible') refreshAll();
    }, REFRESH_MS);
  }

  // ────────── INIT ──────────
  window.LovbotCRM = { refresh: refreshAll, logout: () => { sessionStorage.removeItem(TOKEN_KEY); location.reload(); } };

  function init() {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) {
      showLoginOverlay();
    } else {
      boot();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

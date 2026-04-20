// Panel Loteos — self-service v2
// El cliente edita solo los datos del loteo (nombre, cantidad, ubicación, etc).
// Las tarjetitas del mapa se pintan automáticamente cruzando clientes_activos:
//   - Si un cliente tiene propiedad = "{Loteo} · L-N" → se pinta según estado_pago
//   - Verde: disponible (sin cliente) / Rojo: vendido / Amarillo: reservado (atrasado)
// El cliente asigna lotes desde el CRM de Clientes Activos, no desde Loteos.
(function(){
  let LOTEOS = [];
  let LOTE_ACTUAL = null;              // loteo abierto en modalMapa
  let CLIENTES_CACHE = [];             // cache de clientes_activos

  // ── Utilidades ────────────────────────────────────────────────────────────

  function esUrlMaps(str) {
    if (!str) return false;
    return /^https?:\/\/(www\.)?(google\.[a-z.]+\/maps|maps\.google|maps\.app\.goo\.gl|goo\.gl\/maps)/i.test(str.trim());
  }

  function calcularGrilla(total) {
    const t = parseInt(total) || 0;
    if (t <= 0) return { cols: 0, rows: 0 };
    const maxCols = t <= 25 ? 5 : t <= 64 ? 8 : t <= 144 ? 12 : 16;
    const cols = Math.min(Math.ceil(Math.sqrt(t)), maxCols);
    const rows = Math.ceil(t / cols);
    return { cols, rows };
  }

  // Agrupa N lotes en "manzanas" de ~8 lotes cada una para visual tipo urbanización
  function dividirEnManzanas(total) {
    const t = parseInt(total) || 0;
    if (t <= 0) return [];
    // Manzanas de 8 lotes (2 filas x 4 cols) idealmente
    const lotesPorManzana = t <= 16 ? 4 : t <= 40 ? 6 : 8;
    const manzanas = [];
    let contador = 1;
    while (contador <= t) {
      const hasta = Math.min(contador + lotesPorManzana - 1, t);
      const lotes = [];
      for (let i = contador; i <= hasta; i++) lotes.push(i);
      manzanas.push(lotes);
      contador = hasta + 1;
    }
    return manzanas;
  }

  // Parsea propiedad "San Ignacio Golf & Resort · L-5" → { loteo: "...", nro: "L-5" }
  function parsePropiedad(propiedad) {
    if (!propiedad) return null;
    const parts = propiedad.split('·').map(s => s.trim());
    if (parts.length !== 2) return null;
    return { loteo: parts[0], nro: parts[1] };
  }

  // Cruza clientes con un loteo: devuelve mapa { "L-5": {cliente, estado}, ... }
  function indexarClientesPorLote(loteoNombre) {
    const idx = {};
    CLIENTES_CACHE.forEach(c => {
      const p = parsePropiedad(c.propiedad);
      if (!p) return;
      if (p.loteo !== loteoNombre) return;
      // estado visual: vendido (al_dia/pagado) / atrasado (reservado amarillo) / sin plata (rojo)
      const ep = (c.estado_pago || '').toLowerCase();
      let estado = 'vendido';  // asignado = vendido por default
      if (ep === 'atrasado' || ep === 'moroso' || ep === 'pendiente') estado = 'reservado';
      idx[p.nro] = { cliente: c, estado };
    });
    return idx;
  }

  function contarEstados(total, clientesPorLote) {
    let vendidos = 0, reservados = 0;
    Object.values(clientesPorLote).forEach(x => {
      if (x.estado === 'vendido') vendidos++;
      else if (x.estado === 'reservado') reservados++;
    });
    const libres = total - vendidos - reservados;
    return { libres: Math.max(0, libres), reservados, vendidos };
  }

  // ── Carga combinada: loteos + clientes ────────────────────────────────────

  window.cargarLoteos = async function() {
    try {
      const [loteosData, clientesData] = await Promise.all([
        crmList('loteos'),
        crmFetch('/crm/clientes'),
      ]);
      LOTEOS = loteosData.items || [];
      CLIENTES_CACHE = clientesData.items || clientesData.records || [];
      renderLoteos();
    } catch (e) {
      console.error('[LOTEOS]', e);
      notif('❌ Error cargando loteos', e.message);
    }
  };

  function renderLoteos() {
    const cont = document.getElementById('loteosLista');
    if (!cont) return;
    if (LOTEOS.length === 0) {
      cont.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 gap-5">${renderAddCard()}</div>`;
      return;
    }
    cont.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      ${LOTEOS.map(renderLoteoCard).join('')}
      ${renderAddCard()}
    </div>`;
  }

  function renderAddCard() {
    return `
      <button onclick="abrirModalLoteo()" style="background:rgba(26,29,39,0.4);border:2px dashed var(--brd);border-radius:12px;padding:40px 24px;min-height:340px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;transition:all 0.2s">
        <div style="width:64px;height:64px;border-radius:50%;background:rgba(139,153,250,0.1);display:flex;align-items:center;justify-content:center;margin-bottom:12px">
          <span style="font-size:36px;color:var(--accent);line-height:1">+</span>
        </div>
        <div style="font-size:16px;font-weight:600;color:var(--text)">Agregar nuevo loteo</div>
        <div style="font-size:12px;color:var(--text2);margin-top:4px;text-align:center">Creá un loteo nuevo con su cantidad de lotes</div>
      </button>
    `;
  }

  function renderLoteoCard(l) {
    const total = l.total_lotes || 0;
    // Calcular contadores cruzando con clientes
    const clientesPorLote = indexarClientesPorLote(l.nombre);
    const { libres, reservados, vendidos } = contarEstados(total, clientesPorLote);
    const ocupados = reservados + vendidos;
    const pctOcupado = total > 0 ? Math.round((ocupados / total) * 100) : 0;
    const ubic = l.ubicacion || l.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" style="color:var(--accent);text-decoration:none" onclick="event.stopPropagation()">📍 Ver en Google Maps</a>`
      : `<span>📍 ${ubic || l.ciudad || 'Sin ubicación'}</span>`;

    return `
      <div style="background:var(--surface);border:1px solid var(--brd);border-radius:12px;overflow:hidden;cursor:pointer;transition:all 0.2s" onclick="verMapaLoteo(${l.id})">
        <div style="background:linear-gradient(135deg, rgba(139,153,250,0.15), rgba(34,38,54,0.8));padding:20px 24px">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:8px">
            <div style="flex:1;min-width:0">
              <div style="font-size:18px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${l.nombre}</div>
              <div style="font-size:12px;color:var(--text2);margin-top:4px">${ubicLabel}</div>
            </div>
            <div style="display:flex;gap:4px;flex-shrink:0" onclick="event.stopPropagation()">
              <button onclick='abrirModalLoteo(${JSON.stringify(l).replace(/'/g, "&apos;")})' title="Editar datos del loteo" style="padding:6px 10px;background:rgba(34,38,54,0.7);border:1px solid var(--brd);border-radius:6px;color:var(--text);cursor:pointer;font-size:12px">✏️</button>
              <button onclick="eliminarLoteo(${l.id})" title="Eliminar" style="padding:6px 10px;background:rgba(239,68,68,0.2);border:1px solid rgba(239,68,68,0.3);border-radius:6px;color:#f87171;cursor:pointer;font-size:12px">🗑</button>
            </div>
          </div>
          ${l.descripcion ? `<p style="font-size:12px;color:var(--text2);margin-top:8px;line-height:1.4">${l.descripcion}</p>` : ''}
        </div>
        <div style="padding:20px">
          <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;margin-bottom:8px">
            <span style="color:var(--text2)">${total} lotes totales</span>
            <span style="font-weight:600;color:var(--text)">${pctOcupado}% ocupado</span>
          </div>
          <div style="width:100%;height:6px;background:var(--surface2);border-radius:999px;overflow:hidden;margin-bottom:16px">
            <div style="height:100%;background:linear-gradient(90deg, #16a34a, #eab308);width:${pctOcupado}%;transition:width 0.4s"></div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:8px;margin-bottom:16px">
            <div style="background:rgba(22,163,74,0.1);color:#4ade80;padding:12px 8px;border-radius:6px;text-align:center">
              <div style="font-size:20px;font-weight:700">${libres}</div>
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.05em">Libres</div>
            </div>
            <div style="background:rgba(234,179,8,0.1);color:#facc15;padding:12px 8px;border-radius:6px;text-align:center">
              <div style="font-size:20px;font-weight:700">${reservados}</div>
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.05em">Reservados</div>
            </div>
            <div style="background:rgba(220,38,38,0.1);color:#f87171;padding:12px 8px;border-radius:6px;text-align:center">
              <div style="font-size:20px;font-weight:700">${vendidos}</div>
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.05em">Vendidos</div>
            </div>
          </div>
          <div style="font-size:12px;color:var(--text2);text-align:center">Hacé clic en la tarjeta para ver el mapa del loteo</div>
        </div>
      </div>
    `;
  }

  // ── Modal crear/editar datos del loteo ────────────────────────────────────

  window.abrirModalLoteo = function(data = null) {
    const l = data || {};
    const modal = document.getElementById('modalLoteo');
    if (!modal) return;
    document.getElementById('loteoId').value = l.id || '';
    document.getElementById('loteoNombre').value = l.nombre || '';
    document.getElementById('loteoTotal').value = l.total_lotes || '';
    document.getElementById('loteoCiudad').value = l.ciudad || '';
    document.getElementById('loteoUbicacion').value = l.ubicacion || '';
    document.getElementById('loteoDescripcion').value = l.descripcion || '';
    document.getElementById('loteoSlug').value = l.slug || '';
    abrirModal('modalLoteo');
  };

  window.guardarLoteo = async function() {
    const id = document.getElementById('loteoId').value;
    const nombre = document.getElementById('loteoNombre').value.trim();
    const total = parseInt(document.getElementById('loteoTotal').value) || 0;
    if (!nombre) { notif('❌ Falta el nombre del loteo'); return; }
    if (total <= 0) { notif('❌ La cantidad de lotes debe ser mayor a 0'); return; }
    const slugActual = document.getElementById('loteoSlug').value.trim();
    const campos = {
      nombre,
      slug: slugActual || nombre.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      total_lotes: total,
      ciudad: document.getElementById('loteoCiudad').value.trim(),
      ubicacion: document.getElementById('loteoUbicacion').value.trim(),
      descripcion: document.getElementById('loteoDescripcion').value.trim(),
    };
    try {
      if (id) await crmUpdate('loteos', id, campos);
      else await crmCreate('loteos', campos);
      cerrarModal('modalLoteo');
      notif('✅ Loteo guardado', campos.nombre);
      await cargarLoteos();
      if (LOTE_ACTUAL && id && Number(id) === LOTE_ACTUAL.id) {
        setTimeout(() => verMapaLoteo(LOTE_ACTUAL.id), 300);
      }
    } catch (e) { notif('❌ Error', e.message); }
  };

  window.guardarYCargarLotes = async function() {
    await guardarLoteo();
  };

  window.eliminarLoteo = async function(id) {
    if (!confirm('¿Eliminar este loteo? No afecta a los clientes activos asignados.')) return;
    try {
      await crmDelete('loteos', id);
      notif('✅ Loteo eliminado');
      cargarLoteos();
    } catch (e) { notif('❌ Error', e.message); }
  };

  // ── Mapa del loteo: grilla de tarjetitas (solo lectura, auto-sync) ────────

  window.verMapaLoteo = async function(loteoId) {
    const loteo = LOTEOS.find(l => l.id === loteoId);
    if (!loteo) return;
    LOTE_ACTUAL = loteo;
    // Refrescar clientes para tener datos actualizados
    try {
      const data = await crmFetch('/crm/clientes');
      CLIENTES_CACHE = data.items || data.records || [];
    } catch (e) { /* ignore */ }
    renderMapaLoteo();
    abrirModal('modalMapa');
  };

  function renderLoteTarjeta(nroLoteNum, clientesPorLote) {
    const nroLote = `L-${nroLoteNum}`;
    const asignado = clientesPorLote[nroLote];
    const base = 'position:relative;aspect-ratio:1;border-radius:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;transition:all 0.2s;font-weight:700;padding:4px;color:#fff;font-size:11px;line-height:1;box-shadow:0 2px 4px rgba(0,0,0,0.2);overflow:hidden';
    const hover = 'onmouseover="this.style.transform=\'scale(1.08)\';this.style.zIndex=\'10\';this.style.boxShadow=\'0 6px 16px rgba(0,0,0,0.5)\'" onmouseout="this.style.transform=\'scale(1)\';this.style.zIndex=\'1\';this.style.boxShadow=\'0 2px 4px rgba(0,0,0,0.2)\'"';
    if (asignado) {
      const bg = asignado.estado === 'vendido'
        ? 'linear-gradient(135deg, #dc2626 0%, #991b1b 100%)'
        : 'linear-gradient(135deg, #eab308 0%, #a16207 100%)';
      const border = asignado.estado === 'vendido' ? '#fca5a5' : '#fde047';
      const icono = asignado.estado === 'vendido' ? '🏡' : '⏳';
      const nombre = `${asignado.cliente.nombre || ''} ${asignado.cliente.apellido || ''}`.trim() || 'Cliente';
      return `<button onclick="verInfoClienteLote(${asignado.cliente.id})" title="${nroLote} — ${nombre} (${asignado.estado})"
        style="${base};background:${bg};border:1.5px solid ${border}" ${hover}>
        <span style="font-size:13px;margin-bottom:2px">${icono}</span>
        <span style="font-size:10px;font-weight:800">${nroLote}</span>
      </button>`;
    } else {
      return `<button title="${nroLote} — disponible"
        style="${base};background:linear-gradient(135deg, #22c55e 0%, #15803d 100%);border:1.5px solid #86efac" ${hover}>
        <span style="font-size:13px;margin-bottom:2px">🌳</span>
        <span style="font-size:10px;font-weight:800">${nroLote}</span>
      </button>`;
    }
  }

  function renderMapaLoteo() {
    const loteo = LOTE_ACTUAL;
    const total = loteo.total_lotes || 0;
    const clientesPorLote = indexarClientesPorLote(loteo.nombre);
    const { libres, reservados, vendidos } = contarEstados(total, clientesPorLote);
    const manzanas = dividirEnManzanas(total);

    document.getElementById('mapaTitulo').textContent = `🗺️ ${loteo.nombre}`;
    const ubic = loteo.ubicacion || loteo.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" style="color:var(--accent)">Ver en Google Maps ↗</a>`
      : (ubic || 'Sin ubicación');
    document.getElementById('mapaSubtitulo').innerHTML = `${total} lotes · ${ubicLabel}`;

    // Render manzanas (bloques) con calles virtuales entre ellas
    const manzanasHtml = manzanas.map((lotes, idx) => {
      const letra = String.fromCharCode(65 + idx);  // A, B, C...
      const colsManzana = lotes.length <= 4 ? lotes.length : Math.ceil(lotes.length / 2);
      return `
        <div style="position:relative;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:14px 12px 10px;box-shadow:inset 0 0 40px rgba(0,0,0,0.15)">
          <div style="position:absolute;top:-10px;left:14px;background:var(--surface);color:var(--text2);font-size:10px;font-weight:700;padding:2px 10px;border-radius:10px;border:1px solid var(--brd);letter-spacing:0.1em">MANZANA ${letra}</div>
          <div style="display:grid;gap:6px;grid-template-columns:repeat(${colsManzana}, minmax(48px, 70px));justify-content:center;margin-top:6px">
            ${lotes.map(n => renderLoteTarjeta(n, clientesPorLote)).join('')}
          </div>
        </div>
      `;
    }).join('');

    // Ícono decorativo de "centro" entre manzanas si hay >= 4 manzanas
    const ambientacion = manzanas.length >= 4 ? `
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;opacity:0.06;font-size:180px">🏞️</div>
    ` : '';

    const cont = document.getElementById('mapaContenido');
    cont.innerHTML = `
      <div style="display:flex;gap:16px;font-size:12px;margin-bottom:16px;flex-wrap:wrap;align-items:center;padding:10px 14px;background:var(--surface2);border-radius:10px">
        <span style="display:flex;align-items:center;gap:8px"><span style="font-size:14px">🌳</span><span style="color:#86efac;font-weight:700">${libres}</span>Libres</span>
        <span style="display:flex;align-items:center;gap:8px"><span style="font-size:14px">⏳</span><span style="color:#fde047;font-weight:700">${reservados}</span>Atrasados</span>
        <span style="display:flex;align-items:center;gap:8px"><span style="font-size:14px">🏡</span><span style="color:#fca5a5;font-weight:700">${vendidos}</span>Vendidos</span>
      </div>
      <div style="position:relative;background:
          radial-gradient(ellipse at 20% 30%, rgba(34,197,94,0.08) 0%, transparent 50%),
          radial-gradient(ellipse at 80% 70%, rgba(59,130,246,0.06) 0%, transparent 50%),
          linear-gradient(135deg, #0f1f14 0%, #0a1410 100%);
          border:1px solid rgba(134,239,172,0.15);border-radius:14px;padding:24px;overflow:auto;max-height:68vh;box-shadow:inset 0 0 60px rgba(0,0,0,0.4)">
        ${ambientacion}
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:24px;position:relative;z-index:2">
          ${manzanasHtml}
        </div>
      </div>
      <p style="font-size:12px;color:var(--text2);margin-top:12px;text-align:center">
        💡 Los estados se sincronizan desde <strong>Clientes Activos</strong>.
        Asignás un lote escribiendo en <em>Propiedad</em>: <code style="background:var(--surface2);padding:2px 6px;border-radius:4px">${loteo.nombre} · L-N</code>
      </p>
    `;
  }

  // ── Modal info del cliente (solo lectura) ────────────────────────────────

  window.verInfoClienteLote = function(clienteId) {
    const c = CLIENTES_CACHE.find(x => x.id === clienteId);
    if (!c) return;
    const pct = c.cuotas_total > 0 ? Math.round((c.cuotas_pagadas / c.cuotas_total) * 100) : 0;
    const nombre = `${c.nombre || ''} ${c.apellido || ''}`.trim() || 'Cliente';
    document.getElementById('loteTitulo').textContent = `👤 ${nombre}`;
    document.getElementById('loteSubtitulo').textContent = c.propiedad || '';
    document.getElementById('loteClienteInfoContent').innerHTML = `
      ${c.telefono ? `<div style="margin-bottom:6px">📞 ${c.telefono}</div>` : ''}
      ${c.email ? `<div style="margin-bottom:6px">✉️ ${c.email}</div>` : ''}
      <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><div style="font-size:11px;color:var(--text2)">Estado de pago</div><div style="font-weight:600;margin-top:2px">${c.estado_pago || 'al_dia'}</div></div>
        <div><div style="font-size:11px;color:var(--text2)">Cuotas</div><div style="font-weight:600;margin-top:2px">${c.cuotas_pagadas || 0}/${c.cuotas_total || 0} (${pct}%)</div></div>
        ${c.monto_cuota ? `<div><div style="font-size:11px;color:var(--text2)">Cuota</div><div style="font-weight:600;margin-top:2px">$${c.monto_cuota}</div></div>` : ''}
        ${c.proximo_vencimiento ? `<div><div style="font-size:11px;color:var(--text2)">Próximo vencimiento</div><div style="font-weight:600;margin-top:2px">${c.proximo_vencimiento}</div></div>` : ''}
      </div>
      ${c.notas ? `<div style="margin-top:12px;padding:10px;background:var(--surface2);border-radius:6px;font-size:12px"><strong>Notas:</strong> ${c.notas}</div>` : ''}
    `;
    abrirModal('modalLote');
  };
})();

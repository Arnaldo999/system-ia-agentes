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

  function renderMapaLoteo() {
    const loteo = LOTE_ACTUAL;
    const total = loteo.total_lotes || 0;
    const { cols } = calcularGrilla(total);
    const clientesPorLote = indexarClientesPorLote(loteo.nombre);
    const { libres, reservados, vendidos } = contarEstados(total, clientesPorLote);

    document.getElementById('mapaTitulo').textContent = `🗺️ ${loteo.nombre}`;
    const ubic = loteo.ubicacion || loteo.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" style="color:var(--accent)">Ver en Google Maps ↗</a>`
      : (ubic || 'Sin ubicación');
    document.getElementById('mapaSubtitulo').innerHTML = `${total} lotes · ${ubicLabel}`;

    let tarjetas = '';
    for (let i = 1; i <= total; i++) {
      const nroLote = `L-${i}`;
      const asignado = clientesPorLote[nroLote];
      const baseStyle = 'aspect-ratio:1;border-radius:4px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all 0.15s;font-weight:600;padding:0;color:#fff;font-size:10px;line-height:1';
      if (asignado) {
        const bg = asignado.estado === 'vendido' ? '#dc2626' : '#eab308';
        const nombre = `${asignado.cliente.nombre || ''} ${asignado.cliente.apellido || ''}`.trim() || 'Cliente';
        tarjetas += `<button onclick="verInfoClienteLote(${asignado.cliente.id})" title="${nroLote} — ${nombre} (${asignado.estado})"
          style="${baseStyle};background:${bg};border:1px solid ${bg}">
          <span style="padding:2px">${nroLote}</span>
        </button>`;
      } else {
        tarjetas += `<button title="${nroLote} — disponible"
          style="${baseStyle};background:#16a34a;border:1px solid #16a34a">
          <span style="padding:2px">${nroLote}</span>
        </button>`;
      }
    }

    const cont = document.getElementById('mapaContenido');
    cont.innerHTML = `
      <div style="display:flex;gap:16px;font-size:12px;margin-bottom:16px;flex-wrap:wrap;align-items:center">
        <span style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;background:#16a34a;border-radius:3px"></span>Libres: ${libres}</span>
        <span style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;background:#eab308;border-radius:3px"></span>Reservados (atrasados): ${reservados}</span>
        <span style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;background:#dc2626;border-radius:3px"></span>Vendidos (al día): ${vendidos}</span>
      </div>
      <div style="background:rgba(34,38,54,0.3);border:1px solid var(--brd);border-radius:8px;padding:12px;overflow:auto;max-height:72vh">
        <div style="display:grid;gap:6px;grid-template-columns: repeat(${cols}, minmax(44px, 56px));justify-content:start">
          ${tarjetas}
        </div>
      </div>
      <p style="font-size:12px;color:var(--text2);margin-top:12px">
        💡 Los estados se sincronizan automáticamente desde <strong>Clientes Activos</strong>.
        Para asignar un lote a un cliente, escribí en su campo <em>Propiedad</em>: <code>${loteo.nombre} · L-N</code>
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

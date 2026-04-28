# Plan: Ecosistema digital Grupo Back (7 firmas, multi-marca)

**Estado**: Borrador
**Creado**: 2026-04-27
**Proyecto**: arnaldo
**Cliente**: Grupo Back (Patricia Back / Hernán Weninger)
**Wiki**: [[wiki/entidades/grupo-back]]

---

## Descripción general

Construir un ecosistema digital unificado para **Grupo Back**, un grupo empresarial multi-marca de Posadas (Misiones) con **7 firmas** en 5 rubros distintos + 2 blogs informativos. Es el primer cliente multi-marca/multi-rubro del ecosistema Arnaldo y el más complejo a la fecha.

El ecosistema se ejecuta **secuencialmente** (una firma por vez, no las 7 en paralelo) para mostrar valor rápido y permitir iteración del template entre marcas.

### Las 7 firmas (alcance cerrado 2026-04-27)

| # | Marca | Rubro | Piezas digitales |
|---|-------|-------|-------------------|
| 1 | **Rizoma Propiedades** | Inmobiliaria multi-vertical (toda Misiones) | Sub-sitio + Bot WhatsApp + CRM |
| 2 | **La Misionerita** | Restaurant + parador turístico (contingentes) | Sub-sitio + Bot WhatsApp + CRM |
| 3 | **Patricio's** | Resto-bar + alquiler salones | Sub-sitio + Bot (alcance acotado) + CRM |
| 4 | **La Martina Apart Hotel** | Hospedaje (San Ignacio) | Sub-sitio + CRM reservas (bot a confirmar) |
| 5 | **Bocanada** | Panadería/pastelería | Sub-sitio + CRM pedidos (bot a confirmar) |
| 6 | **Club Progreso** | Club fútbol | Solo blog informativo |
| 7 | **Fundación Misión Emprender** | Educativa | Solo blog + calendario público |

### Dominio

`grupoback.com` — disponible, propuesto por Arnaldo, le gusta a Hernán. **Pendiente confirmación de Patricia**.

---

## Estado actual (qué existe hoy)

- ✅ Hoja de ruta v2 publicada en `backends/system-ia-agentes/clientes-publicos/patricia-back/roadmap.html` → URL pública `https://agentes.arnaldoayalaestratega.cloud/propuestas/patricia-back/roadmap.html`
- ✅ Wiki del cliente: [[wiki/entidades/grupo-back]] + [[patricia-back]] + [[hernan-weninger]]
- ✅ Sesión 2026-04-27 ingestada: [[wiki/fuentes/sesion-2026-04-27-grupo-back-confirmacion]]
- ✅ Reunión presencial 2026-04-27 14:30 en La Misionerita — alcance cerrado
- ✅ Checklist de reunión rellenable: `clientes/patricia-back/checklist-reunion-2026-04-27.html`
- ⏳ Cotización oficial pendiente (Cotizador de Arnaldo en su instancia n8n)
- ⏳ Contrato con cláusula de tratamiento de datos pendiente
- ⏳ Compra de dominio pendiente
- ⏳ Estructura legal/marca paraguas pendiente confirmación de Patricia
- ⏳ Asesores responsables por marca pendientes

### Referencia técnica (uso interno — NO mencionar a Patricia)

- **Maicol / Back Urbanizaciones** ([[maicol]]): inmobiliaria 1 marca con bot WhatsApp + CRM Airtable + YCloud + Coolify Hostinger. Es referencia técnica interna nuestra para acelerar Rizoma — alquileres + ventas + asesorías similares. **Nunca mencionar este cliente a Patricia ni en docs cliente-facing** (regla de aislamiento entre clientes).
- **Cesar Posada** ([[cesar-posada]]): cliente turismo en pre-onboarding con propuesta enviada.

---

## Cambios propuestos

### Archivos a crear (estructura del proyecto)

```
01_PROYECTOS/01_ARNALDO_AGENCIA/
├── clientes/patricia-back/
│   ├── Brief.txt                              ✅ ya existe (notas internas)
│   └── checklist-reunion-2026-04-27.html      ✅ ya existe (uso interno)
└── backends/system-ia-agentes/
    ├── clientes-publicos/patricia-back/       ← FUENTE ÚNICA cliente-facing
    │   ├── roadmap.html                       ✅ v2 publicado
    │   ├── propuesta.html                     ⏳ a crear
    │   ├── brief-rizoma.html                  ⏳ a crear (Fase Rizoma)
    │   ├── brief-misionerita.html             ⏳ a crear (Fase Misionerita)
    │   └── brief-patricios.html               ⏳ a crear (Fase Patricio's)
    └── workers/clientes/arnaldo/grupo-back/
        ├── rizoma/worker.py                   ⏳ Fase Rizoma
        ├── misionerita/worker.py              ⏳ Fase Misionerita
        └── patricios/worker.py                ⏳ Fase Patricio's
```

> **Regla**: archivos cliente-facing (roadmap, propuesta, briefs públicos) viven SOLO en `clientes-publicos/{slug}/` → no duplicar en `clientes/{slug}/`. La carpeta `clientes/{slug}/` queda para notas internas (`Brief.txt`, checklists, briefs recibidos del cliente).

### Sitio web multi-marca (Coolify Hostinger Arnaldo)

URL futura: `grupoback.com` servida desde el monorepo backend Arnaldo bajo:
```
clientes-publicos/grupo-back/
├── index.html              # home del grupo (skin neutro)
├── rizoma/                 # sub-sitio Rizoma
├── misionerita/
├── patricios/
├── martina/
├── bocanada/
├── club-progreso/
└── mision-emprender/
```

### Decisión técnica clave: BD Airtable vs PostgreSQL

| Factor | Airtable | PostgreSQL dedicado |
|--------|----------|----------------------|
| Stack estándar Arnaldo | ✅ | ❌ rompe estándar |
| Persona única + roles polimórficos cross-marca | ⚠️ posible con linked records pero feo | ✅ nativo (probado en Robert) |
| Sidebar multi-marca con CRM | ⚠️ se puede pero limita filtros complejos | ✅ |
| Onboarding del cliente para cargar contenido | ✅ Airtable es UI-friendly | ❌ requiere CRM frontend nuestro |
| Costo operativo mensual | ⚠️ ~$20/mes/base × 5 marcas con CRM = ~$100/mes | ✅ ~$10/mes VPS compartido |
| Velocidad de desarrollo | ✅ rápido (no hay que armar admin) | ⚠️ más lento (CRM frontend completo) |

**Decisión propuesta**: **Airtable** para Grupo Back en esta primera iteración.

**Justificación**:
1. Base técnica pre-construida → tiempo de implementación ~2 días Rizoma (5-10 días total ecosistema completo)
2. La "ficha única cross-marca" se puede armar con una base Airtable única "Personas" con linked records a las bases de cada marca
3. Patricia/Hernán no piden frontend custom — quieren operativa, no panel sofisticado
4. Si después escala mucho (>10k contactos cross-marca, performance), migramos a Postgres en una v2

⚠️ Si Patricia exige sidebar tipo CRM v3 Robert con UX premium, ahí sí justifica Postgres + frontend HTML+Tailwind. **Validar con ella en cotización**.

---

## Decisiones de diseño + alternativas consideradas

### 1. ¿Bot único multi-rubro vs bots separados?
- **Opción A** (descartada): un solo bot router que detecta intención y cambia tono. Era la idea original de la hoja de ruta v1.
- **Opción B** (elegida): **5 bots separados** (Rizoma + Misionerita + Patricio's + Martina + Bocanada) cada uno con su número WhatsApp, prompt y razonamiento. **Decisión confirmada de Hernán/Patricia 2026-04-27 tarde**.
- Trade-off: más bots = más mantenimiento, pero cada uno hace mejor su trabajo, mantiene identidad de marca y facilita métricas independientes.

### 2. ¿1 número WhatsApp para los 5 bots o 5 números separados?
- **Decisión confirmada 2026-04-27 tarde**: **1 número por servicio** = 5 números YCloud distintos (Rizoma, Misionerita, Patricio's, Martina, Bocanada).
- Justificación: cada marca conserva su identidad propia + permite escalar/dar de baja un servicio sin afectar a los demás + facilita métricas independientes por marca.
- Impacto en cronograma: 5 onboardings YCloud (cada uno requiere validación de número con código SMS + alta del template). Hernán/Patricia deben proveer los 5 números antes de arrancar la fase de cada marca.

### 3. ¿Cuándo arranca la 1ª marca?
- Después de: contrato firmado + 1er pago + dominio comprado + brief Rizoma completado.
- ETA: Rizoma en ~2 días desde el arranque. Ecosistema completo en 5-10 días de implementación activa.

### 4. Orden propuesto de las 7 marcas
1. Rizoma (más rentable, modelo Maicol probado)
2. Misionerita (temporada activa de tours, retorno inmediato)
3. Patricio's (alcance acotado, bot simple)
4. Martina (reservas hospedaje)
5. Bocanada (pedidos panadería)
6. Club Progreso + Fundación (en paralelo, son blogs)

**Patricia tiene la última palabra sobre el orden** — esto es propuesta.

---

## Preguntas abiertas (bloqueos antes de ejecutar)

| # | Pregunta | Bloqueante para | Quién contesta |
|---|----------|------------------|------------------|
| 1 | ¿Patricia confirma `grupoback.com` como dominio? | Compra dominio + DNS | Patricia |
| 2 | ¿Estructura legal — 1 CUIT o varios? | Contrato + facturación | Patricia |
| 3 | ~~¿WhatsApp: 1 número o 5 separados?~~ ✅ DECIDIDO 2026-04-27: **5 números separados, 1 por bot** | — | — |
| 4 | ¿Quién es el asesor responsable de cada marca? | Routing de leads en CRM | Patricia |
| 5 | ¿Orden definitivo de construcción? | Cronograma | Patricia |
| 6 | ¿BD: Airtable (recomendado) o Postgres dedicado? | Stack técnico | Arnaldo (técnico) |
| 7 | ¿Cláusula tratamiento de datos — texto exacto? | Contrato | Arnaldo (con asesor legal si aplica) |
| 8 | ¿Hay datos viejos para migrar (Excel, planillas)? | Carga inicial | Patricia/Hernán |
| 9 | ¿Logos y colores existen o hay que diseñar? | Brief de identidad visual | Patricia |
| 10 | ¿Precio cotizado vs presupuesto del cliente? | Firma de contrato | Cotizador Arnaldo + Patricia |

---

## Tareas paso a paso

### Fase 0 — Pre-implementación (antes de codear)

- [ ] **0.1** Patricia confirma alcance final (preguntas 1-5 arriba)
- [ ] **0.2** Cotizar con Cotizador Arnaldo (instancia n8n) — desglose por marca
- [ ] **0.3** Redactar contrato con cláusula tratamiento de datos
- [ ] **0.4** Patricia firma + paga implementación de Rizoma (1ª marca)
- [ ] **0.5** Comprar dominio `grupoback.com`
- [ ] **0.6** Crear repo/branch del cliente en backend Arnaldo
- [ ] **0.7** Crear formulario de brief Rizoma (formato HTML como Cesar Posada) → Patricia lo completa
- [ ] **0.8** Cuando llegue brief: actualizar wiki [[grupo-back]] con datos reales

### Fase Rizoma Propiedades (~2 días)

> Estructura inmobiliaria multi-vertical: alquileres + ventas + servicios + tasaciones. Ya tenemos infraestructura base pre-construida del ecosistema, así que la implementación se acelera.

- [ ] **R.1** Leer playbook [[wiki/playbooks/airtable-schema-setup]] + crear base Airtable Rizoma desde el modelo inmobiliario base del ecosistema
- [ ] **R.2** Adaptar schema Airtable Rizoma (tablas: Propiedades, Alquileres, Servicios, Asesorías, Tasaciones, Leads, Conversaciones)
- [ ] **R.3** Crear worker FastAPI `workers/clientes/arnaldo/grupo-back/rizoma/worker.py` desde el modelo base del ecosistema
- [ ] **R.4** Adaptar prompt BANT del bot Rizoma (calificación de leads inmobiliarios + alquileres + servicios)
- [ ] **R.5** Onboarding YCloud — número Rizoma (o sub-número compartido si decisión 3 fue compartido)
- [ ] **R.6** Sub-sitio `clientes-publicos/grupo-back/rizoma/` con catálogo + CTA WhatsApp
- [ ] **R.7** Deploy Coolify Hostinger Arnaldo
- [ ] **R.8** Testing con Patricia/Hernán (envíos prueba al bot)
- [ ] **R.9** Capacitación del equipo Rizoma (uso del CRM Airtable)
- [ ] **R.10** Go-live + soporte 7 días post-lanzamiento

### Fase La Misionerita (~1-2 días)

> Vertical gastro/turismo. Reservas + agenda contingentes + carta online. Como ya levantamos infraestructura base con Rizoma, esta marca reusa todo y solo cambia el dominio del prompt + schema.

- [ ] **M.1** Crear playbook nicho gastronomía-turismo (a sumar en `wiki/playbooks/`)
- [ ] **M.2** Schema Airtable La Misionerita (tablas: Reservas, Contingentes, Empresas turísticas, Menús, Asesores)
- [ ] **M.3** Worker `misionerita/worker.py` con prompt adaptado a reservas + contingentes
- [ ] **M.4** Integración Cal.com para "Visita grupal Misionerita"
- [ ] **M.5** Sub-sitio con carta online + reservas + sección "Empresas turísticas" para agendar visitas
- [ ] **M.6** Onboarding WhatsApp + deploy + testing
- [ ] **M.7** Capacitación + go-live

### Fase Patricio's (~1 día)

> Bot acotado: solo alquiler salón + ofertas catering.

- [ ] **P.1** Schema Airtable (Salones, Reservas, Catering, Eventos)
- [ ] **P.2** Worker `patricios/worker.py` con prompt acotado (solo alquiler salón → no responder por carta o reservas resto-bar)
- [ ] **P.3** Cal.com "Cita alquiler salón Patricio's"
- [ ] **P.4** Sub-sitio + carta online (si hay tiempo) + CTA bot
- [ ] **P.5** Deploy + testing + go-live

### Fase Martina + Bocanada (~2 días total)

- [ ] **MA.1** Schema Airtable Martina (Departamentos, Reservas, Huéspedes)
- [ ] **MA.2** Si Patricia confirma bot → worker Martina; si no, solo CRM + sub-sitio con formulario web
- [ ] **MA.3** Sub-sitio Martina + go-live
- [ ] **BO.1** Schema Airtable Bocanada (Productos, Pedidos, Clientes recurrentes)
- [ ] **BO.2** Worker Bocanada o CRM con form web
- [ ] **BO.3** Sub-sitio Bocanada + go-live

### Fase Blogs Club Progreso + Fundación (~1 día, en paralelo)

- [ ] **B.1** Sub-sitio Club Progreso (blog estático con secciones por categoría)
- [ ] **B.2** Sub-sitio Fundación con calendario público de cursos (puede ser embed de Cal.com con vista calendario)
- [ ] **B.3** Deploy + go-live ambos

### Fase Final — Integración cross-marca

- [ ] **F.1** Base Airtable "Personas" cross-marca con linked records a todas las bases marca
- [ ] **F.2** CRM frontend HTML+Tailwind (si se decide hacerlo) consumiendo todas las bases con sidebar por marca
- [ ] **F.3** Documentación operativa para Patricia/Hernán
- [ ] **F.4** Soporte continuo mensual

---

## Conexiones y dependencias

### Stack cliente-facing comunicado a Patricia/Hernán (y stack técnico real)

| Capa | Lo que ve el cliente | Stack técnico real |
|------|---------------------|-------------------|
| Sitio web | WordPress + dominio `grupoback.com` + hosting | WordPress en VPS Arnaldo |
| Automatizaciones | n8n — conecta todo | [[wiki/conceptos/n8n]] instancia Arnaldo en VPS |
| Servidor | VPS dedicado, aislado | VPS Hostinger Arnaldo |
| Bots/CRM | Coolify | [[wiki/entidades/coolify-arnaldo]] |
| Base de datos | Airtable | [[wiki/conceptos/airtable]] — 1 base por marca |
| WhatsApp | 5 números (1 por bot) | [[wiki/conceptos/ycloud]] — 5 onboardings |
| Seguridad | Capas de seguridad | HTTPS/SSL, tokens protegidos, backups diarios, aislamiento físico |
| LLM | — | OpenAI Arnaldo |
| Agenda | — | Cal.com Arnaldo (compartido) |
| Worker | — | FastAPI monorepo `workers/clientes/arnaldo/grupo-back/` |
| CRM frontend | — | HTML + Tailwind CDN según [[wiki/playbooks/crm-html-tailwind]] |

### Playbooks que vamos a leer durante la ejecución
- [[wiki/playbooks/airtable-schema-setup]] — schema cliente
- [[wiki/playbooks/worker-whatsapp-bot]] — bot WhatsApp
- [[wiki/playbooks/crm-html-tailwind]] — CRM frontend (Fase Final)
- [[wiki/playbooks/propuesta-cliente-coolify]] — sub-sitios

### Memoria/feedback que aplica
- [memory/feedback_REGLA_demo_primero.md](demo primero) — desarrollar workers en `demos/` antes de copiarlos a `clientes/grupo-back/`
- [memory/feedback_REGLA_aislamiento_cliente_facing.md](aislamiento) — nunca mencionar Robert/Mica en material que ve Patricia
- [memory/feedback_clausula_tratamiento_datos_es_argumento_venta.md](cláusula datos) — incluir cláusula en propuesta + contrato
- [memory/feedback_REGLA_python311_fstring_triples.md](python 3.11) — Coolify usa 3.11, cuidado con f-strings anidados

---

## Lista de validación

### Antes de cerrar Fase 0
- [ ] Las 10 preguntas abiertas tienen respuesta o decisión arquitectónica documentada
- [ ] Cotización aceptada por Patricia
- [ ] Contrato firmado con cláusula de datos
- [ ] Pago de implementación de Rizoma recibido
- [ ] Dominio comprado y apuntado a Coolify Arnaldo

### Antes de cada go-live de marca
- [ ] Brief de la marca completado por Patricia/Hernán
- [ ] Schema BD revisado y aprobado por Arnaldo (sin campos olvidados)
- [ ] Bot probado con al menos 5 conversaciones de prueba realistas
- [ ] Sub-sitio responsive en celular y desktop
- [ ] Cal.com configurado con tipos de evento de la marca
- [ ] Equipo del cliente capacitado para usar Airtable
- [ ] Cláusula de datos revisada y aprobada (firma de Patricia ya cubre esto)

---

## Criterios de éxito

### Por fase de marca
- ✅ Bot responde correctamente al menos 80% de consultas de prueba sin escalar
- ✅ Sub-sitio carga en menos de 3 segundos en celular
- ✅ Cal.com agenda eventos sin doble booking
- ✅ Patricia y Hernán pueden cargar/editar contenido en Airtable sin pedir ayuda

### Globales del proyecto
- ✅ 1ª marca (Rizoma) andando en producción en los primeros días tras la firma
- ✅ Ecosistema completo (7 marcas) funcionando en **5 a 10 días de implementación** total
- ✅ Cero data leaks entre marcas (cada base aislada)
- ✅ Patricia firma ampliación a más marcas / mantenimiento mensual continuo

---

## Notas de implementación

_(Esta sección se llena durante la ejecución, no al planificar.)_

### Desviaciones esperadas
- Patricia tiende a expandir alcance — si después de la marca 3 aparece un "8º negocio", **renegociar antes de sumar**.
- Si en testing Rizoma sale más rápido de lo previsto, considerar arrancar Misionerita en paralelo para acelerar.
- Si Patricia exige CRM frontend tipo Robert (sidebar fancy), reabrir decisión Airtable vs Postgres antes de Fase Final.

### Bloqueos que pueden aparecer
- WhatsApp Business Platform: si Patricia quiere 5 números separados, puede haber demoras de aprobación de Meta de varios días por número.
- Coolify Hostinger: límites de RAM compartida — monitorear si los 3 workers + sub-sitios + n8n no pegan al techo.
- Airtable: el plan free tiene límites de records (~1200 por base) → puede que necesitemos plan team ($20/mes/base).

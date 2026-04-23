-- ============================================================
-- Schema: lovbot_agencia
-- BD: lovbot_agencia (SEPARADA de lovbot_crm_modelo)
-- Proposito: CRM propio de Lovbot como agencia.
--            Funnel de prospectos y clientes que contratan
--            el producto Lovbot (no el CRM inmobiliario de
--            sus clientes finales).
-- Entorno: PostgreSQL en VPS Hetzner (lovbot-postgres)
-- Fecha propuesta: 2026-04-23
-- ============================================================
-- INSTRUCCIONES DE APLICACION:
--   1. Aprobar este schema con Robert / Arnaldo.
--   2. Crear la BD:  CREATE DATABASE lovbot_agencia;
--   3. Conectar:     psql -U lovbot -d lovbot_agencia
--   4. Ejecutar:     \i schema_lovbot_agencia.sql
-- NO ejecutar en lovbot_crm_modelo ni en robert_crm.
-- ============================================================


-- ── 1. FUENTES DE LEAD ──────────────────────────────────────
-- Catalogo de canales/fuentes de adquisicion.
-- Evita strings libres en agencia_leads.canal_origen.
CREATE TABLE IF NOT EXISTS agencia_fuentes (
    id          SERIAL PRIMARY KEY,
    slug        VARCHAR(60) UNIQUE NOT NULL,  -- ej: 'landing', 'fb_ads', 'referido'
    nombre      VARCHAR(120) NOT NULL,        -- ej: 'Landing lovbot.ai'
    descripcion TEXT,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fuentes iniciales del mockup actual del frontend
INSERT INTO agencia_fuentes (slug, nombre) VALUES
    ('landing',       'Landing lovbot.ai'),
    ('bot_whatsapp',  'Bot WhatsApp'),
    ('referido',      'Referido'),
    ('fb_ads',        'Facebook / Instagram Ads'),
    ('evento',        'Evento / Networking'),
    ('lead_center',   'Lead.center (FB Lead Ads)'),
    ('zapier',        'Zapier / automatizacion'),
    ('otro',          'Otro')
ON CONFLICT (slug) DO NOTHING;


-- ── 2. LEADS DE AGENCIA ──────────────────────────────────────
-- Prospecto que llega a Lovbot interesado en contratar el producto.
-- Un lead puede ser una inmobiliaria, agencia, desarrolladora, agente.
-- Funnel: lead → contactado → propuesta → negociacion → cliente | perdido
CREATE TABLE IF NOT EXISTS agencia_leads (
    id              SERIAL PRIMARY KEY,

    -- Identificacion del prospecto
    nombre_empresa  VARCHAR(150),                          -- ej: "Inmobiliaria Vega"
    nombre_contacto VARCHAR(150) NOT NULL,                 -- persona de contacto
    apellido_contacto VARCHAR(100),
    whatsapp        VARCHAR(30),                           -- con codigo de pais: +521...
    email           VARCHAR(150),
    ciudad          VARCHAR(100),
    pais            VARCHAR(60) DEFAULT 'Mexico',

    -- Clasificacion
    fuente_id       INTEGER REFERENCES agencia_fuentes(id) ON DELETE SET NULL,
    canal_raw       VARCHAR(80),                           -- valor raw si fuente_id es NULL
    tipo_cliente    VARCHAR(40) DEFAULT 'inmobiliaria'
                    CHECK (tipo_cliente IN (
                        'inmobiliaria','agencia','desarrolladora',
                        'agente_independiente','otro'
                    )),

    -- Etapa del funnel
    estado          VARCHAR(30) NOT NULL DEFAULT 'lead'
                    CHECK (estado IN (
                        'lead',          -- recien captado
                        'contactado',    -- primer contacto realizado
                        'propuesta',     -- propuesta enviada
                        'negociacion',   -- en negociacion activa
                        'cliente',       -- cerrado — se convirtio en cliente
                        'perdido'        -- no compro
                    )),

    -- Motivo de perdida (solo si estado='perdido')
    motivo_perdida  VARCHAR(120),                          -- ej: "Fue a Hubspot", "Sin presupuesto"

    -- Trazabilidad a cliente
    cliente_id      INTEGER,                               -- FK a agencia_clientes.id (se llena al convertir)

    -- BANT / calificacion
    presupuesto_aprox VARCHAR(60),                         -- ej: "USD 300/mes", "a consultar"
    decision_estimada DATE,                                -- fecha estimada de decision

    -- Seguimiento
    proximo_contacto DATE,                                 -- fecha para el proximo follow-up
    responsable      VARCHAR(100) DEFAULT 'Robert',        -- quien lleva este lead

    -- Notas libres
    notas           TEXT,

    -- Integracion futura
    fb_lead_id      VARCHAR(100),                         -- ID del lead en Facebook Lead Ads
    lead_center_id  VARCHAR(100),                         -- ID en lead.center (futuro conector)
    zapier_data     JSONB,                                -- payload raw de Zapier si aplica

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agencia_leads_estado     ON agencia_leads(estado);
CREATE INDEX IF NOT EXISTS idx_agencia_leads_fuente     ON agencia_leads(fuente_id);
CREATE INDEX IF NOT EXISTS idx_agencia_leads_whatsapp   ON agencia_leads(whatsapp);
CREATE INDEX IF NOT EXISTS idx_agencia_leads_responsable ON agencia_leads(responsable);
CREATE INDEX IF NOT EXISTS idx_agencia_leads_proximo    ON agencia_leads(proximo_contacto);


-- ── 3. CLIENTES DE AGENCIA ───────────────────────────────────
-- Cliente que ya cerro y tiene acceso activo al producto Lovbot.
-- Se crea al convertir un lead (estado='cliente').
-- Tiene trazabilidad al lead de origen via lead_origen_id.
CREATE TABLE IF NOT EXISTS agencia_clientes (
    id              SERIAL PRIMARY KEY,

    -- Datos del cliente
    nombre_empresa  VARCHAR(150),
    nombre_contacto VARCHAR(150) NOT NULL,
    apellido_contacto VARCHAR(100),
    whatsapp        VARCHAR(30),
    email           VARCHAR(150),
    ciudad          VARCHAR(100),
    pais            VARCHAR(60) DEFAULT 'Mexico',

    -- Trazabilidad desde lead
    lead_origen_id  INTEGER REFERENCES agencia_leads(id) ON DELETE SET NULL,
    fuente_id       INTEGER REFERENCES agencia_fuentes(id) ON DELETE SET NULL,

    -- Producto contratado
    plan            VARCHAR(60) DEFAULT 'crm_basico'
                    CHECK (plan IN (
                        'crm_basico',       -- CRM inmobiliario solo
                        'crm_bot',          -- CRM + bot WhatsApp
                        'crm_bot_full',     -- CRM + bot + automatizaciones full
                        'personalizado'     -- acuerdo custom
                    )),

    -- Economia del contrato
    monto_implementacion DECIMAL(12,2),                   -- pago unico inicial
    monto_mensual        DECIMAL(12,2),                   -- cuota de mantenimiento
    moneda               VARCHAR(5) DEFAULT 'USD',
    fecha_inicio_contrato DATE,
    fecha_renovacion      DATE,

    -- Supabase tenant (vincula con el CRM SaaS)
    tenant_slug     VARCHAR(80) UNIQUE,                   -- ej: 'vega-inmo'
    db_nombre       VARCHAR(80),                          -- ej: 'vega_crm' en Hetzner

    -- Estado operativo
    estado          VARCHAR(30) DEFAULT 'activo'
                    CHECK (estado IN (
                        'activo',           -- pagando y usando
                        'trial',            -- en periodo de prueba
                        'pausado',          -- pago pendiente / en disputa
                        'cancelado'         -- baja definitiva
                    )),

    -- Integracion
    numero_waba     VARCHAR(30),                          -- numero WhatsApp del cliente (WABA)
    waba_phone_id   VARCHAR(60),                          -- phone_number_id Meta
    waba_conectado  BOOLEAN DEFAULT FALSE,

    -- Seguimiento
    responsable     VARCHAR(100) DEFAULT 'Robert',
    notas           TEXT,
    nps             SMALLINT CHECK (nps BETWEEN 0 AND 10),-- Net Promoter Score

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agencia_clientes_estado  ON agencia_clientes(estado);
CREATE INDEX IF NOT EXISTS idx_agencia_clientes_plan    ON agencia_clientes(plan);
CREATE INDEX IF NOT EXISTS idx_agencia_clientes_tenant  ON agencia_clientes(tenant_slug);


-- ── 4. LOG DE CONTACTOS ──────────────────────────────────────
-- Registro cronologico de cada interaccion con un lead o cliente.
-- Canal: WhatsApp, llamada, reunion, email, etc.
-- Aplica tanto a leads (pre-cierre) como a clientes (post-cierre).
CREATE TABLE IF NOT EXISTS agencia_contactos_log (
    id              SERIAL PRIMARY KEY,

    -- Referencia polimorfica: puede apuntar a lead o a cliente
    entidad_tipo    VARCHAR(20) NOT NULL
                    CHECK (entidad_tipo IN ('lead', 'cliente')),
    entidad_id      INTEGER NOT NULL,             -- id en agencia_leads o agencia_clientes

    -- Tipo de interaccion
    tipo_contacto   VARCHAR(40) NOT NULL
                    CHECK (tipo_contacto IN (
                        'whatsapp_saliente',
                        'whatsapp_entrante',
                        'llamada_saliente',
                        'llamada_entrante',
                        'reunion_presencial',
                        'reunion_virtual',
                        'email_saliente',
                        'email_entrante',
                        'demo_enviada',
                        'propuesta_enviada',
                        'nota_interna'
                    )),

    -- Contenido
    resumen         TEXT,                         -- resumen breve de la interaccion
    resultado       VARCHAR(60),                  -- ej: 'interesado', 'no contesto', 'pide demo'
    duracion_min    SMALLINT,                     -- duracion en minutos (para llamadas/reuniones)

    -- Seguimiento generado por esta interaccion
    proximo_contacto DATE,                        -- si de esta accion surge un follow-up
    proximo_accion  VARCHAR(120),                 -- descripcion del proximo paso

    -- Quien lo registro
    responsable     VARCHAR(100) DEFAULT 'Robert',
    fecha_contacto  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contactos_log_entidad ON agencia_contactos_log(entidad_tipo, entidad_id);
CREATE INDEX IF NOT EXISTS idx_contactos_log_fecha   ON agencia_contactos_log(fecha_contacto);


-- ── 5. PROPUESTAS / DEALS ────────────────────────────────────
-- Propuestas formales enviadas a un lead.
-- Un lead puede recibir multiples versiones de propuesta.
CREATE TABLE IF NOT EXISTS agencia_propuestas (
    id              SERIAL PRIMARY KEY,

    -- Referencia al lead (siempre al lead, incluso si ya se convirtio)
    lead_id         INTEGER REFERENCES agencia_leads(id) ON DELETE CASCADE,

    -- Datos de la propuesta
    version         SMALLINT DEFAULT 1,                   -- v1, v2, v3...
    titulo          VARCHAR(200),                         -- ej: "Propuesta CRM+Bot — Inmobiliaria Vega"

    -- Economia
    monto_implementacion DECIMAL(12,2),
    monto_mensual        DECIMAL(12,2),
    moneda               VARCHAR(5) DEFAULT 'USD',
    incluye_bot          BOOLEAN DEFAULT TRUE,
    incluye_crm          BOOLEAN DEFAULT TRUE,
    descripcion_alcance  TEXT,                            -- qué está incluido en esta propuesta

    -- Estado
    estado          VARCHAR(30) DEFAULT 'borrador'
                    CHECK (estado IN (
                        'borrador',
                        'enviada',
                        'vista',        -- cliente confirmo que la vio
                        'aceptada',
                        'rechazada',
                        'vencida'       -- paso el tiempo sin respuesta
                    )),
    fecha_envio     DATE,
    fecha_vencimiento DATE,             -- deadline de validez de la propuesta
    fecha_respuesta DATE,

    -- Archivo
    pdf_url         TEXT,               -- link a la propuesta en PDF (Cloudinary u otro)

    -- Notas
    notas           TEXT,
    responsable     VARCHAR(100) DEFAULT 'Robert',

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_propuestas_lead    ON agencia_propuestas(lead_id);
CREATE INDEX IF NOT EXISTS idx_propuestas_estado  ON agencia_propuestas(estado);


-- ── 6. PAGOS DE CLIENTES ─────────────────────────────────────
-- Registro de cobros mensuales de mantenimiento por cliente.
-- Permite saber quién está al día y quién atrasado.
CREATE TABLE IF NOT EXISTS agencia_pagos (
    id              SERIAL PRIMARY KEY,

    cliente_id      INTEGER REFERENCES agencia_clientes(id) ON DELETE CASCADE,

    -- Periodo
    periodo_mes     SMALLINT NOT NULL CHECK (periodo_mes BETWEEN 1 AND 12),
    periodo_anio    SMALLINT NOT NULL,

    -- Monto
    monto           DECIMAL(12,2) NOT NULL,
    moneda          VARCHAR(5) DEFAULT 'USD',

    -- Estado del cobro
    estado          VARCHAR(20) DEFAULT 'pendiente'
                    CHECK (estado IN (
                        'pendiente',
                        'pagado',
                        'atrasado',
                        'perdonado'     -- descuento o condonacion
                    )),
    fecha_pago      DATE,               -- fecha real del pago recibido
    metodo_pago     VARCHAR(40),        -- ej: 'transferencia', 'efectivo', 'paypal'

    notas           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pagos_cliente     ON agencia_pagos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_pagos_estado      ON agencia_pagos(estado);
CREATE INDEX IF NOT EXISTS idx_pagos_periodo     ON agencia_pagos(periodo_anio, periodo_mes);


-- ── 7. VISTA UTILITARIA: FUNNEL RESUMEN ──────────────────────
-- Vista de lectura rapida del embudo (equivale a las cards del frontend).
-- No requiere JOINs complejos desde el frontend.
CREATE OR REPLACE VIEW agencia_funnel_resumen AS
SELECT
    estado,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE proximo_contacto <= CURRENT_DATE) AS con_followup_vencido
FROM agencia_leads
GROUP BY estado
ORDER BY CASE estado
    WHEN 'lead'        THEN 1
    WHEN 'contactado'  THEN 2
    WHEN 'propuesta'   THEN 3
    WHEN 'negociacion' THEN 4
    WHEN 'cliente'     THEN 5
    WHEN 'perdido'     THEN 6
    ELSE 7
END;


-- ── 8. TRIGGER: updated_at automatico ───────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_agencia_leads_upd
    BEFORE UPDATE ON agencia_leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_agencia_clientes_upd
    BEFORE UPDATE ON agencia_clientes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_agencia_propuestas_upd
    BEFORE UPDATE ON agencia_propuestas
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── FIN DEL SCHEMA ───────────────────────────────────────────
-- Proximos pasos:
--   1. Aprobar este archivo.
--   2. Crear BD: CREATE DATABASE lovbot_agencia;
--   3. Ejecutar este script.
--   4. Crear router FastAPI en:
--      workers/clientes/lovbot/agencia_crm/router.py
--   5. Conectar frontend agencia.html a:
--      agentes.lovbot.ai/agencia/leads   (GET/POST/PATCH)
--      agentes.lovbot.ai/agencia/funnel  (GET — usa la vista)
--      agentes.lovbot.ai/agencia/clientes (GET/POST/PATCH)
--      agentes.lovbot.ai/agencia/contactos-log (POST)
--      agentes.lovbot.ai/agencia/propuestas (GET/POST/PATCH)
-- ============================================================

"""
DB PostgreSQL — Mica / System IA — Bot Sessions
================================================
Persistencia de sesiones de conversación WhatsApp entre deploys.
Un solo PostgreSQL en Coolify Arnaldo (Hostinger) compartido entre
todos los clientes de Mica, separados por tenant (MICA_TENANT_SLUG).

Conexión: env vars MICA_PG_HOST/PORT/DB/USER/PASS
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# ── Config ────────────────────────────────────────────────────────────────────
PG_HOST = os.environ.get("MICA_PG_HOST", "")
PG_PORT = os.environ.get("MICA_PG_PORT", "5432")
PG_DB   = os.environ.get("MICA_PG_DB", "system_ia_db")
PG_USER = os.environ.get("MICA_PG_USER", "system_ia")
PG_PASS = os.environ.get("MICA_PG_PASS", "")

TENANT = os.environ.get("MICA_TENANT_SLUG", "demo")


def _conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
        connect_timeout=8,
    )


def _available() -> bool:
    return bool(PG_HOST and PG_PASS)


# ── BOT SESSIONS ──────────────────────────────────────────────────────────────

def setup_bot_sessions():
    """Crea tabla bot_sessions si no existe."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_sessions (
                telefono     TEXT NOT NULL,
                tenant       TEXT NOT NULL,
                sesion_data  JSONB NOT NULL DEFAULT '{}',
                historial    JSONB NOT NULL DEFAULT '[]',
                updated_at   TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (telefono, tenant)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_sessions_tenant
            ON bot_sessions(tenant)
        """)
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DB-MICA] Tabla bot_sessions lista (tenant={TENANT}).")
    except Exception as e:
        print(f"[DB-MICA] Error setup_bot_sessions: {e}")


def get_bot_session(telefono: str) -> dict:
    """Carga sesión y historial desde PostgreSQL."""
    if not _available():
        return {}
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT sesion_data, historial FROM bot_sessions WHERE telefono = %s AND tenant = %s",
            (telefono, TENANT),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {}
        sesion = row["sesion_data"] if isinstance(row["sesion_data"], dict) else json.loads(row["sesion_data"])
        historial = row["historial"] if isinstance(row["historial"], list) else json.loads(row["historial"])
        return {"sesion": sesion, "historial": historial}
    except Exception as e:
        print(f"[DB-MICA] Error get_bot_session ({telefono}): {e}")
        return {}


def save_bot_session(telefono: str, sesion: dict, historial: list) -> None:
    """Upsert sesión + historial. Llamar desde background thread."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bot_sessions (telefono, tenant, sesion_data, historial, updated_at)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, NOW())
            ON CONFLICT (telefono, tenant) DO UPDATE SET
                sesion_data = EXCLUDED.sesion_data,
                historial   = EXCLUDED.historial,
                updated_at  = NOW()
        """, (telefono, TENANT, json.dumps(sesion, default=str), json.dumps(historial)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB-MICA] Error save_bot_session ({telefono}): {e}")


def delete_bot_session(telefono: str) -> None:
    """Elimina sesión cuando el lead se califica o cierra."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM bot_sessions WHERE telefono = %s AND tenant = %s",
            (telefono, TENANT),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB-MICA] Error delete_bot_session ({telefono}): {e}")

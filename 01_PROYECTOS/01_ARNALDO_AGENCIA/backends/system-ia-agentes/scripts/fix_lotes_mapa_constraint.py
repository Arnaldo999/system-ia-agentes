"""
Fix: UNIQUE constraint de lotes_mapa — incluir manzana en la clave
==================================================================
El constraint anterior era (tenant_slug, loteo_id, numero_lote), lo que
impedia que A-9 y B-9 coexistieran en el mismo loteo. En planos reales
cada manzana tiene su propia numeracion 1..N, entonces A-1, B-1, C-1
son lotes distintos y deben poder convivir.

Nuevo constraint: (tenant_slug, loteo_id, manzana, numero_lote)

Idempotente:
  - Elimina el constraint viejo SI existe (uq_lotes_mapa_loteo_nro).
  - Crea el constraint nuevo SI NO existe ya (uq_lotes_mapa_tenant_loteo_manzana_nro).

Uso:
  python fix_lotes_mapa_constraint.py
  (requiere env vars LOVBOT_PG_*)
"""

import os
import sys
import psycopg2

PG_HOST = os.environ.get("LOVBOT_PG_HOST", "localhost")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_DB   = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")

CONSTRAINT_VIEJO = "uq_lotes_mapa_loteo_nro"
CONSTRAINT_NUEVO = "uq_lotes_mapa_tenant_loteo_manzana_nro"


def _conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
        connect_timeout=10,
    )


def _constraint_existe(cur, nombre: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM pg_constraint WHERE conname = %s",
        (nombre,),
    )
    return cur.fetchone()[0] > 0


def fix_constraint():
    if not PG_PASS:
        print("[FIX] ERROR: LOVBOT_PG_PASS no configurado.")
        sys.exit(1)

    conn = _conn()
    cur = conn.cursor()

    # 1. Eliminar constraint viejo si existe
    if _constraint_existe(cur, CONSTRAINT_VIEJO):
        print(f"[FIX] Eliminando constraint viejo: {CONSTRAINT_VIEJO} ...")
        cur.execute(
            f"ALTER TABLE lotes_mapa DROP CONSTRAINT IF EXISTS {CONSTRAINT_VIEJO}"
        )
        conn.commit()
        print(f"[FIX] Constraint {CONSTRAINT_VIEJO} eliminado.")
    else:
        print(f"[FIX] Constraint viejo '{CONSTRAINT_VIEJO}' no existe — omitiendo.")

    # 2. Crear constraint nuevo si no existe
    if _constraint_existe(cur, CONSTRAINT_NUEVO):
        print(f"[FIX] Constraint nuevo '{CONSTRAINT_NUEVO}' ya existe — OK, nada que hacer.")
    else:
        print(f"[FIX] Creando constraint nuevo: {CONSTRAINT_NUEVO} ...")
        cur.execute(f"""
            ALTER TABLE lotes_mapa
            ADD CONSTRAINT {CONSTRAINT_NUEVO}
            UNIQUE (tenant_slug, loteo_id, manzana, numero_lote)
        """)
        conn.commit()
        print(f"[FIX] Constraint {CONSTRAINT_NUEVO} creado correctamente.")

    cur.close()
    conn.close()
    print("[FIX] Listo.")


if __name__ == "__main__":
    fix_constraint()

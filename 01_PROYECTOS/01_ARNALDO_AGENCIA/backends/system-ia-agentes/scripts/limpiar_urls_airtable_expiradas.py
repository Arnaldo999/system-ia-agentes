"""
limpiar_urls_airtable_expiradas.py
====================================
Limpia URLs de imágenes de Airtable expiradas de la DB lovbot_crm_modelo.

Las URLs firmadas de Airtable tienen TTL ~2h. Cuando se migraron datos de
Airtable -> PostgreSQL se copiaron las URLs tal cual. Ahora generan HTTP 410.

Operación:
  - Detecta automáticamente columnas de texto en `propiedades` (via information_schema)
  - Pone NULL en cualquier celda que contenga 'airtableusercontent.com' o 'v5.airtable'
  - Reporta cuántas filas tocó por columna
  - Idempotente: correrlo dos veces no cambia nada si ya está limpio

Uso:
  python scripts/limpiar_urls_airtable_expiradas.py [--db lovbot_crm_modelo]

Variables de entorno requeridas (mismas que el worker):
  LOVBOT_PG_HOST, LOVBOT_PG_PORT, LOVBOT_PG_USER, LOVBOT_PG_PASS, LOVBOT_PG_DB (override por --db)
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

# ── Config ────────────────────────────────────────────────────────────────────
PG_HOST = os.environ.get("LOVBOT_PG_HOST", "localhost")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")

# Patrones de URLs Airtable expiradas
URL_PATTERNS = ["%airtableusercontent.com%", "%v5.airtable%"]

# Tablas y columnas conocidas con imágenes (se amplía con discovery automático)
TABLA_PRINCIPAL = "propiedades"
COLS_CONOCIDAS = ["imagen_url", "imagen", "foto", "foto_principal", "Imagen_URL", "Foto", "Imagen"]


def get_conn(dbname: str):
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=dbname,
        user=PG_USER, password=PG_PASS,
        connect_timeout=8,
    )


def discover_text_columns(cur, tabla: str) -> list[str]:
    """Devuelve todas las columnas de tipo texto de la tabla via information_schema."""
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
          AND data_type IN ('text', 'character varying', 'varchar', 'character', 'char')
        ORDER BY ordinal_position
    """, (tabla,))
    return [row["column_name"] for row in cur.fetchall()]


def limpiar_urls_en_columna(cur, tabla: str, columna: str) -> int:
    """
    Pone NULL en la columna donde el valor contiene URLs de Airtable.
    Retorna cantidad de filas afectadas.
    """
    conditions = " OR ".join([f'"{columna}" ILIKE %s' for _ in URL_PATTERNS])
    sql = f'UPDATE "{tabla}" SET "{columna}" = NULL WHERE ({conditions}) AND "{columna}" IS NOT NULL'
    try:
        cur.execute(sql, URL_PATTERNS)
        return cur.rowcount
    except psycopg2.Error as e:
        # Columna no existe u otro error — ignorar silenciosamente
        print(f"  [SKIP] {tabla}.{columna}: {e.pgerror or str(e)}")
        return 0


def run(dbname: str, dry_run: bool = False) -> dict:
    """
    Ejecuta la limpieza. Retorna resumen { columna: filas_afectadas }.
    """
    print(f"\n[limpiar-urls-airtable] DB={dbname} dry_run={dry_run}")
    conn = get_conn(dbname)
    conn.autocommit = False
    results = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Discovery automático de columnas de texto
            text_cols = discover_text_columns(cur, TABLA_PRINCIPAL)
            print(f"  Columnas de texto encontradas en '{TABLA_PRINCIPAL}': {text_cols}")

            for col in text_cols:
                count = limpiar_urls_en_columna(cur, TABLA_PRINCIPAL, col)
                if count > 0:
                    results[col] = count
                    print(f"  [LIMPIADO] {TABLA_PRINCIPAL}.{col}: {count} fila(s)")

        if dry_run:
            conn.rollback()
            print("  [DRY RUN] Cambios revertidos.")
        else:
            conn.commit()
            print(f"  [OK] Commit realizado. Total columnas afectadas: {len(results)}")

    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] {e}")
        raise
    finally:
        conn.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Limpia URLs Airtable expiradas de PostgreSQL Lovbot")
    parser.add_argument("--db", default=os.environ.get("LOVBOT_PG_DB", "lovbot_crm_modelo"),
                        help="Nombre de la base de datos (default: lovbot_crm_modelo)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra qué haría pero no comitea")
    args = parser.parse_args()

    if not PG_PASS:
        print("[ERROR] LOVBOT_PG_PASS no configurado. Exportar variables de entorno.")
        sys.exit(1)

    results = run(dbname=args.db, dry_run=args.dry_run)

    if results:
        print("\nResumen de filas limpiadas:")
        for col, count in results.items():
            print(f"  {col}: {count}")
    else:
        print("\nNo se encontraron URLs Airtable expiradas. DB ya estaba limpia.")

    return results


if __name__ == "__main__":
    main()

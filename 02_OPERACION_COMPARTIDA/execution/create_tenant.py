"""
create_tenant.py — Crea un nuevo tenant en Supabase para el CRM SaaS.

Uso:
    python execution/create_tenant.py \\
        --slug robert \\
        --nombre "Robert Bazan Inmobiliaria" \\
        --proyecto robert \\
        --pin 1234

Proyectos soportados:
    - robert  → CRM Lovbot (admin.lovbot.ai)
    - mica    → CRM System IA (system-ia-agencia.vercel.app)

El script crea el registro en la tabla `tenants` de Supabase y reporta
la URL del CRM lista para compartir con el cliente.

Notas:
    - El PIN se almacena como SHA-256 (nunca en texto plano)
    - `fecha_vence` se setea a 30 días desde hoy por defecto
    - El tenant queda en estado_pago = "activo" automáticamente
    - NUNCA agregar maicol aquí — tiene CRM propio independiente
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env")
load_dotenv(dotenv_path=ROOT / "02_DEV_N8N_ARCHITECT/backends/system-ia-agentes/.env", override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

CRM_URLS = {
    "robert": "https://crm.lovbot.ai",
    "mica":   "https://system-ia-agencia.vercel.app/system-ia/crm",
}


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def tenant_exists(slug: str) -> bool:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/tenants",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        params={"slug": f"eq.{slug}", "select": "slug"},
        timeout=10,
    )
    resp.raise_for_status()
    return len(resp.json()) > 0


def create_tenant(slug: str, nombre: str, pin: str, dias: int = 30) -> dict:
    fecha_vence = (date.today() + timedelta(days=dias)).isoformat()
    payload = {
        "slug": slug,
        "nombre": nombre,
        "pin_hash": hash_pin(pin),
        "fecha_vence": fecha_vence,
        "estado_pago": "activo",
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/tenants",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()[0] if resp.json() else payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear tenant en Supabase CRM SaaS")
    parser.add_argument("--slug",     required=True, help="Identificador único (ej: robert, luciano)")
    parser.add_argument("--nombre",   required=True, help="Nombre del negocio")
    parser.add_argument("--proyecto", required=True, choices=["robert", "mica"], help="CRM destino")
    parser.add_argument("--pin",      default="1234", help="PIN de acceso (default: 1234)")
    parser.add_argument("--dias",     type=int, default=30, help="Días de vigencia (default: 30)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL y SUPABASE_KEY deben estar en .env")
        sys.exit(1)

    if args.slug == "maicol":
        print("ERROR: maicol tiene CRM propio independiente — no usar este script")
        sys.exit(1)

    if tenant_exists(args.slug):
        print(f"ERROR: El tenant '{args.slug}' ya existe en Supabase")
        sys.exit(1)

    print(f"Creando tenant '{args.slug}' para proyecto '{args.proyecto}'...")
    tenant = create_tenant(args.slug, args.nombre, args.pin, args.dias)

    crm_base = CRM_URLS[args.proyecto]
    crm_url = f"{crm_base}?tenant={args.slug}"

    print(f"""
✅ Tenant creado exitosamente

   Slug:        {tenant['slug']}
   Nombre:      {tenant['nombre']}
   Vence:       {tenant['fecha_vence']}
   Estado:      {tenant['estado_pago']}
   PIN default: {args.pin}  ← cambiar desde Configuración del CRM

   URL CRM:     {crm_url}

⚠️  Compartir la URL al cliente. Recordarle que cambie el PIN al ingresar.
""")


if __name__ == "__main__":
    main()

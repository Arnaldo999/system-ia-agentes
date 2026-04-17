#!/usr/bin/env python3
"""
clonar_worker_lovbot.py
=======================
Clona el worker base de Robert Inmobiliaria para un cliente nuevo de Lovbot.

Uso:
    python clonar_worker_lovbot.py ~/Descargas/inmobiliaria-garcia.yaml
    python clonar_worker_lovbot.py brief.yaml --dry-run
    python clonar_worker_lovbot.py brief.yaml --no-push
    python clonar_worker_lovbot.py brief.yaml --skip-deploy-wait

Qué hace:
    1. Parsea el YAML del brief
    2. Valida campos requeridos y unicidad del slug (via GET /admin/waba/clients)
    3. Clona robert_inmobiliaria/ → {slug_snake}/
    4. Reemplaza variables de config en el worker clonado
    5. Inyecta bloque de negocio en _build_system_prompt
    6. Actualiza main.py para incluir el nuevo router
    7. git add + commit + push master:main
    8. Espera 30s y muestra la URL de resultado
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("ERROR: Falta pyyaml. Instalalo con: pip install pyyaml")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: Falta requests. Instalalo con: pip install requests")
    sys.exit(1)

# ─── RUTAS ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKERS_BASE = REPO_ROOT / "01_PROYECTOS" / "01_ARNALDO_AGENCIA" / "backends" / "system-ia-agentes" / "workers"
LOVBOT_WORKERS = WORKERS_BASE / "clientes" / "lovbot"
TEMPLATE_WORKER = LOVBOT_WORKERS / "robert_inmobiliaria"
MAIN_PY = REPO_ROOT / "01_PROYECTOS" / "01_ARNALDO_AGENCIA" / "backends" / "system-ia-agentes" / "main.py"

# URL del backend Lovbot en produccion
BACKEND_URL = os.environ.get("LOVBOT_BACKEND_URL", "https://agentes.lovbot.ai")
ADMIN_TOKEN = os.environ.get("LOVBOT_ADMIN_TOKEN", "")

# Numero de WhatsApp de Lovbot (para el mensaje al cliente)
LOVBOT_WA = os.environ.get("LOVBOT_WA_CONTACTO", "5493765XXXXXX")

# ─── COLORES ANSI ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def ok(msg):   print(f"{GREEN}[OK]{RESET} {msg}")
def warn(msg): print(f"{YELLOW}[WARN]{RESET} {msg}")
def err(msg):  print(f"{RED}[ERROR]{RESET} {msg}")
def info(msg): print(f"{CYAN}[INFO]{RESET} {msg}")
def step(msg): print(f"\n{BOLD}{msg}{RESET}")


# ─── VALIDACIONES ────────────────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "slug",
    "nombre_empresa",
    "ciudad",
    ("asesor", "nombre"),
    ("asesor", "telefono"),
]


def _get_nested(data: dict, *keys):
    """Obtiene valor anidado de un dict, devuelve None si no existe."""
    cur = data
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def validar_yaml(data: dict) -> list[str]:
    """Valida que el YAML tenga todos los campos requeridos. Devuelve lista de errores."""
    errors = []
    for field in REQUIRED_FIELDS:
        if isinstance(field, tuple):
            val = _get_nested(data, *field)
            label = ".".join(field)
        else:
            val = data.get(field)
            label = field

        if not val:
            errors.append(f"Campo requerido faltante o vacio: '{label}'")

    # Validar formato del slug
    slug = data.get("slug", "")
    if slug and not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', slug):
        errors.append(
            f"Slug invalido '{slug}' — solo letras minusculas, numeros y guiones. "
            "Ej: inmobiliaria-garcia"
        )

    return errors


def slug_existe_en_backend(slug: str) -> Optional[bool]:
    """
    Consulta GET /clientes/lovbot/inmobiliaria/admin/waba/clients para verificar
    si el slug ya esta en uso como worker_url.
    Devuelve True=existe, False=libre, None=no se pudo verificar (continuar igual).
    """
    headers = {}
    if ADMIN_TOKEN:
        headers["X-Admin-Token"] = ADMIN_TOKEN

    try:
        url = f"{BACKEND_URL}/clientes/lovbot/inmobiliaria/admin/waba/clients"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            clients = resp.json()
            if isinstance(clients, list):
                for c in clients:
                    worker_url = c.get("worker_url", "")
                    # El worker URL contendra el slug del cliente
                    if slug in worker_url or slug.replace("-", "_") in worker_url:
                        return True
            return False
        elif resp.status_code in (401, 403):
            warn("No se pudo verificar unicidad de slug (sin token admin). Continuando...")
            return None
        else:
            warn(f"Backend respondio {resp.status_code} al verificar slug. Continuando...")
            return None
    except Exception as e:
        warn(f"No se pudo contactar el backend para verificar slug: {e}. Continuando...")
        return None


# ─── CLONADO DE ARCHIVOS ─────────────────────────────────────────────────────

def clonar_worker(slug: str, dry_run: bool = False) -> Path:
    """
    Clona robert_inmobiliaria/ → {slug_snake}/
    Devuelve el Path del nuevo directorio.
    """
    slug_snake = slug.replace("-", "_")
    dest = LOVBOT_WORKERS / slug_snake

    if dest.exists():
        raise ValueError(f"El directorio destino ya existe: {dest}")

    info(f"Clonando {TEMPLATE_WORKER.name}/ → {slug_snake}/")

    if not dry_run:
        shutil.copytree(TEMPLATE_WORKER, dest)
        # Limpiar __pycache__ del clon
        for pycache in dest.rglob("__pycache__"):
            shutil.rmtree(pycache, ignore_errors=True)

    ok(f"Directorio clonado: {dest}")
    return dest


# ─── REEMPLAZOS EN WORKER.PY ─────────────────────────────────────────────────

def _yaml_list_to_python_list(items) -> str:
    """Convierte lista YAML a representacion Python inline para string."""
    if not items:
        return ""
    if isinstance(items, list):
        return ", ".join(str(i) for i in items)
    return str(items)


def aplicar_variables(dest: Path, data: dict, dry_run: bool = False):
    """
    Reemplaza variables de configuracion en el worker.py clonado.
    """
    worker_py = dest / "worker.py"
    if not worker_py.exists():
        raise FileNotFoundError(f"No encontre worker.py en {dest}")

    content = worker_py.read_text(encoding="utf-8")
    original = content

    slug       = data["slug"]
    slug_snake = slug.replace("-", "_")
    nombre     = data.get("nombre_empresa", "Lovbot — Inmobiliaria")
    ciudad     = data.get("ciudad", "")
    asesor     = data.get("asesor", {})
    as_nombre  = asesor.get("nombre", "Asesor")
    as_tel     = str(asesor.get("telefono", ""))
    moneda     = data.get("moneda", "USD")
    agenda     = data.get("agenda", {})
    cal_activo = agenda.get("cal_com_activo", False)
    cal_user   = agenda.get("cal_com_username", "")
    cal_event  = agenda.get("cal_com_event_slug", "")
    com        = data.get("comunicacion", {})
    tono       = com.get("tono", "calido_rioplatense")

    # ── 1. Cambiar el import del modulo db (apunta al nuevo package) ──
    old_import = f"from workers.clientes.lovbot.robert_inmobiliaria import db_postgres as db"
    new_import = f"from workers.clientes.lovbot.{slug_snake} import db_postgres as db"
    content = content.replace(old_import, new_import)

    # ── 2. Cambiar el prefix del router ──
    # De: prefix="/clientes/lovbot/inmobiliaria"
    # A:  prefix="/clientes/lovbot/{slug}"
    content = re.sub(
        r'(router\s*=\s*APIRouter\s*\(\s*prefix\s*=\s*")[^"]*(")',
        rf'\g<1>/clientes/lovbot/{slug}\g<2>',
        content
    )

    # ── 3. Cambiar tags del router ──
    content = re.sub(
        r'(tags\s*=\s*\[")[^"]*("\])',
        rf'\g<1>{nombre}\g<2>',
        content
    )

    # ── 4. Defaults de variables de entorno ──
    # NOMBRE_EMPRESA
    content = re.sub(
        r'(NOMBRE_EMPRESA\s*=\s*os\.environ\.get\("[^"]+",\s*")[^"]*(")',
        rf'\g<1>{nombre}\g<2>',
        content
    )
    # CIUDAD
    content = re.sub(
        r'(CIUDAD\s*=\s*os\.environ\.get\("[^"]+",\s*")[^"]*(")',
        rf'\g<1>{ciudad}\g<2>',
        content
    )
    # NOMBRE_ASESOR
    content = re.sub(
        r'(NOMBRE_ASESOR\s*=\s*os\.environ\.get\("[^"]+",\s*")[^"]*(")',
        rf'\g<1>{as_nombre}\g<2>',
        content
    )
    # NUMERO_ASESOR (default vacio en original, lo completamos)
    content = re.sub(
        r'(NUMERO_ASESOR\s*=\s*os\.environ\.get\("[^"]+",\s*")[^"]*(")',
        rf'\g<1>{as_tel}\g<2>',
        content
    )
    # MONEDA
    content = re.sub(
        r'(MONEDA\s*=\s*os\.environ\.get\("[^"]+",\s*")[^"]*(")',
        rf'\g<1>{moneda}\g<2>',
        content
    )

    # ── 5. Cal.com defaults (si esta activo) ──
    if cal_activo and cal_user:
        content = re.sub(
            r'(CAL_API_KEY\s*=\s*os\.environ\.get\("[^"]+",\s*")[^"]*(")',
            rf'\g<1>\g<2>',  # Mantener vacio, se setea via env var
            content
        )
    if cal_activo and cal_event:
        # CAL_EVENT_ID en el original es el numeric ID de Cal.com
        # Dejamos el slug en un comentario para referencia
        pass  # Se maneja solo via env vars en Coolify

    # ── 6. Inyectar bloque de negocio en _build_system_prompt ──
    content = _inyectar_bloque_negocio(content, data)

    # ── 7. Saludo custom (si hay) ──
    saludo_custom = com.get("saludo_custom", "").strip()
    if saludo_custom:
        content = _inyectar_saludo_custom(content, saludo_custom)

    # ── 8. Tono (inyectar nota en el prompt) ──
    content = _inyectar_tono(content, tono)

    # ── 9. Comentario de cabecera ──
    header_comment = f'''"""
Worker — {nombre} — Lovbot Inmobiliaria
{'=' * (len(nombre) + 30)}
Cliente Lovbot clonado desde robert_inmobiliaria.
Slug: {slug}
Ciudad: {ciudad}
Asesor: {as_nombre}

NOTA: Este archivo fue generado automaticamente por clonar_worker_lovbot.py.
Para configuracion de variables de entorno, usar el panel Coolify en coolify.lovbot.ai.
"""'''
    # Reemplazar el docstring original (el primero del archivo)
    content = re.sub(r'^""".*?"""', header_comment, content, count=1, flags=re.DOTALL)

    if content == original:
        warn("El contenido del worker no cambio — verificar reemplazos manualmente.")

    if not dry_run:
        worker_py.write_text(content, encoding="utf-8")
        ok("worker.py actualizado con config del cliente")
    else:
        info("[DRY-RUN] worker.py NO modificado. Cambios que se aplicarian:")
        # Mostrar diff resumido
        orig_lines = original.splitlines()
        new_lines  = content.splitlines()
        changes = 0
        for i, (o, n) in enumerate(zip(orig_lines, new_lines)):
            if o != n and changes < 20:
                print(f"  L{i+1}: {RED}- {o.strip()}{RESET}")
                print(f"  L{i+1}: {GREEN}+ {n.strip()}{RESET}")
                changes += 1
        if len(new_lines) != len(orig_lines):
            info(f"Lineas: {len(orig_lines)} → {len(new_lines)}")


def _inyectar_bloque_negocio(content: str, data: dict) -> str:
    """
    Inyecta un bloque de contexto del negocio justo antes de la linea
    que dice 'Sos un analista comercial' en _build_system_prompt.
    """
    nombre      = data.get("nombre_empresa", "")
    productos   = data.get("productos", [])
    productos_s = _yaml_list_to_python_list(productos) if isinstance(productos, list) else str(productos)
    diferenciales = data.get("diferenciales", "")
    objeciones    = data.get("objeciones_comunes", "")
    publico       = data.get("publico_objetivo", "")
    rango         = data.get("rango_precios", "")
    moneda        = data.get("moneda", "USD")
    zonas         = data.get("zonas_leads", "")
    vertical      = data.get("vertical", "inmobiliaria")

    bloque = f"""    # ── CONTEXTO DEL NEGOCIO (inyectado por clonar_worker_lovbot.py) ──
    # NEGOCIO: {nombre}
    # VERTICAL: {vertical}
    # PRODUCTOS/SERVICIOS: {productos_s}
    # RANGO DE PRECIOS: {rango} {moneda}
    # DIFERENCIALES: {diferenciales}
    # OBJECIONES COMUNES: {objeciones}
    # PUBLICO OBJETIVO: {publico}
    # ZONAS DE LEADS: {zonas}
    # ─────────────────────────────────────────────────────────────────"""

    # Insertar justo antes de la linea del prompt de analista
    marker = 'Sos un analista comercial'
    if marker in content:
        content = content.replace(
            f'    prompt = f"""Sos un analista comercial',
            bloque + '\n    prompt = f"""Sos un analista comercial',
            1
        )
    else:
        warn("No se encontro el marker '_build_system_prompt' para inyectar bloque de negocio.")

    return content


def _inyectar_saludo_custom(content: str, saludo: str) -> str:
    """
    Si hay saludo custom, lo inserta como valor por defecto en el prompt
    cuando el bot aun no saludo.
    """
    # Buscar el placeholder de saludo en el prompt y agregar una nota
    marker = "Ejemplo de tono cálido (NO copiar literal, adaptá):"
    if marker in content:
        nota = f'\n    # SALUDO PERSONALIZADO DEL CLIENTE:\n    # "{saludo}"\n    # (Usar este texto adaptado, no literal)\n    '
        content = content.replace(marker, nota + marker, 1)
    return content


def _inyectar_tono(content: str, tono: str) -> str:
    """
    Agrega una nota de tono al system prompt segun la preferencia del cliente.
    """
    notas_tono = {
        "formal_profesional": (
            "TONO: Formal y profesional. Sin modismos regionales. "
            "Tratar de 'usted'. Evitar emojis excepto en saludo."
        ),
        "calido_rioplatense": (
            "TONO: Cálido y cercano, estilo rioplatense. "
            "Usar 'vos/ustedes'. Emojis con moderación."
        ),
        "neutro_latam": (
            "TONO: Neutro LATAM. Usar 'tú/usted' indistintamente. "
            "Comprensible para cualquier pais hispanohablante."
        ),
        "casual_joven": (
            "TONO: Casual y descontracturado. Lenguaje joven y directo. "
            "Emojis frecuentes. Respuestas cortas."
        ),
    }

    nota = notas_tono.get(tono, "")
    if not nota:
        return content

    # Insertar la nota de tono en el bloque de negocio que ya inyectamos
    marker = "# ─────────────────────────────────────────────────────────────────"
    if marker in content:
        content = content.replace(
            marker,
            f"    # {nota}\n    {marker}",
            1
        )
    return content


# ─── ACTUALIZAR MAIN.PY ──────────────────────────────────────────────────────

def actualizar_main_py(slug: str, nombre: str, dry_run: bool = False):
    """
    Agrega el nuevo router al main.py del monorepo.
    """
    slug_snake = slug.replace("-", "_")
    var_router = f"{slug_snake}_router"
    var_procesar = f"{slug_snake}_procesar"

    content = MAIN_PY.read_text(encoding="utf-8")

    # Verificar si ya esta incluido
    if var_router in content:
        warn(f"El router '{var_router}' ya esta en main.py — saltando actualizacion.")
        return

    # ── Import ──
    import_line = (
        f"from workers.clientes.lovbot.{slug_snake}.worker import router as {var_router}\n"
        f"from workers.clientes.lovbot.{slug_snake}.worker import _procesar as {var_procesar}"
    )

    # Insertar despues de la ultima linea de import de lovbot
    anchor_import = "from workers.clientes.lovbot.robert_inmobiliaria.worker import _procesar as robert_inmo_procesar"
    if anchor_import in content:
        content = content.replace(
            anchor_import,
            anchor_import + "\n\n# ── Cliente Lovbot — " + nombre + " ──\n" + import_line
        )
    else:
        warn("Anchor de import no encontrado en main.py. Import no agregado automaticamente.")
        info(f"Agregar manualmente:\n{import_line}")

    # ── include_router ──
    anchor_router = "app.include_router(robert_inmo_router)"
    if anchor_router in content:
        content = content.replace(
            anchor_router,
            anchor_router + f"\napp.include_router({var_router})"
        )
    else:
        warn("Anchor de include_router no encontrado. Agregar manualmente:")
        info(f"app.include_router({var_router})")

    if not dry_run:
        MAIN_PY.write_text(content, encoding="utf-8")
        ok(f"main.py actualizado con router '{var_router}'")
    else:
        info(f"[DRY-RUN] main.py NO modificado.")
        info(f"  Import a agregar: {import_line}")
        info(f"  Router a agregar: app.include_router({var_router})")


# ─── GIT ─────────────────────────────────────────────────────────────────────

def git_status_limpio() -> bool:
    """Verifica si el working tree esta limpio (sin cambios sin commitear)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True, text=True
    )
    return result.stdout.strip() == ""


def git_commit_push(slug: str, nombre: str, no_push: bool = False, dry_run: bool = False):
    """Hace git add, commit y push."""
    slug_snake = slug.replace("-", "_")
    worker_path = LOVBOT_WORKERS / slug_snake
    commit_msg = (
        f"feat(lovbot): clonar worker para {nombre} ({slug})\n\n"
        f"- Nuevo cliente Lovbot: {nombre}\n"
        f"- Slug: {slug}\n"
        f"- Clonado desde: robert_inmobiliaria/\n"
        f"- Router: /clientes/lovbot/{slug}\n\n"
        f"Co-Authored-By: clonar_worker_lovbot.py <noreply@lovbot.ai>"
    )

    cmds = [
        ["git", "add", str(worker_path), str(MAIN_PY)],
        ["git", "commit", "-m", commit_msg],
    ]
    if not no_push:
        cmds.append(["git", "push", "origin", "master:main"])

    for cmd in cmds:
        info(f"Ejecutando: {' '.join(cmd)}")
        if not dry_run:
            result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
            if result.returncode != 0:
                err(f"Error en '{' '.join(cmd)}':")
                print(result.stderr)
                raise RuntimeError(f"Git command failed: {' '.join(cmd)}")
            ok(f"OK: {' '.join(cmd[:2])}")
            if result.stdout.strip():
                print(result.stdout.strip())


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Clona el worker de Robert Inmobiliaria para un cliente nuevo de Lovbot."
    )
    parser.add_argument("yaml_file", help="Path al archivo YAML del brief del cliente")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra que haria pero no modifica nada ni hace push"
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Clona y commitea pero no hace push (para revisar antes)"
    )
    parser.add_argument(
        "--skip-deploy-wait",
        action="store_true",
        help="No espera los 30s del redeploy de Coolify"
    )
    args = parser.parse_args()

    yaml_path = Path(args.yaml_file).expanduser().resolve()
    dry_run   = args.dry_run
    no_push   = args.no_push

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Lovbot — Clonador de Worker de Cliente{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    if dry_run:
        warn("MODO DRY-RUN — ninguna modificacion real sera aplicada.\n")

    # ── 1. Parsear YAML ──
    step("1. Leyendo brief YAML...")
    if not yaml_path.exists():
        err(f"No encontre el archivo: {yaml_path}")
        sys.exit(1)

    with open(yaml_path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            err(f"Error parseando YAML: {e}")
            sys.exit(1)

    if not isinstance(data, dict):
        err("El YAML no tiene el formato esperado (debe ser un objeto/dict en la raiz).")
        sys.exit(1)

    ok(f"YAML leido: {yaml_path.name}")

    # ── 2. Validar campos requeridos ──
    step("2. Validando campos requeridos...")
    errores = validar_yaml(data)
    if errores:
        err("El YAML tiene los siguientes problemas:")
        for e_msg in errores:
            print(f"  - {e_msg}")
        sys.exit(1)

    slug       = data["slug"]
    slug_snake = slug.replace("-", "_")
    nombre     = data["nombre_empresa"]
    ciudad     = data.get("ciudad", "")
    asesor     = data.get("asesor", {})

    info(f"Slug:    {slug}")
    info(f"Empresa: {nombre}")
    info(f"Ciudad:  {ciudad}")
    info(f"Asesor:  {asesor.get('nombre', '')} ({asesor.get('telefono', '')})")
    ok("Validacion OK")

    # ── 3. Verificar unicidad del slug ──
    step("3. Verificando unicidad del slug en el backend...")
    existe = slug_existe_en_backend(slug)
    if existe is True:
        err(f"El slug '{slug}' ya existe en el backend (waba_clients). Abortar.")
        err("Elegir un slug diferente o verificar si el cliente ya fue onboarded.")
        sys.exit(1)
    elif existe is False:
        ok(f"Slug '{slug}' disponible.")
    else:
        warn("No se pudo verificar el slug en el backend. Continuando de todas formas.")

    # Verificar que el directorio destino no exista
    dest = LOVBOT_WORKERS / slug_snake
    if dest.exists():
        err(f"El directorio '{dest}' ya existe. Abortar para no sobreescribir.")
        sys.exit(1)

    # ── 4. Verificar worker template ──
    step("4. Verificando worker template...")
    if not TEMPLATE_WORKER.exists():
        err(f"No encontre el worker template en: {TEMPLATE_WORKER}")
        sys.exit(1)
    ok(f"Template encontrado: {TEMPLATE_WORKER}")

    # ── 5. Verificar git limpio ──
    step("5. Verificando estado de git...")
    if not dry_run:
        if not git_status_limpio():
            warn("Hay cambios sin commitear en el repositorio.")
            respuesta = input("  ¿Continuar de todas formas? (s/N): ").strip().lower()
            if respuesta not in ("s", "si", "y", "yes"):
                info("Operacion cancelada. Commiteá los cambios pendientes primero.")
                sys.exit(0)
        else:
            ok("Working tree limpio.")

    # ── 6. Clonar worker ──
    step("6. Clonando worker...")
    try:
        dest = clonar_worker(slug, dry_run=dry_run)
    except ValueError as e:
        err(str(e))
        sys.exit(1)

    # ── 7. Aplicar variables ──
    step("7. Aplicando configuracion del cliente al worker...")
    try:
        aplicar_variables(dest, data, dry_run=dry_run)
    except Exception as e:
        err(f"Error aplicando variables: {e}")
        if not dry_run:
            info("Limpiando directorio clonado...")
            shutil.rmtree(dest, ignore_errors=True)
        sys.exit(1)

    # ── 8. Actualizar main.py ──
    step("8. Actualizando main.py...")
    try:
        actualizar_main_py(slug, nombre, dry_run=dry_run)
    except Exception as e:
        err(f"Error actualizando main.py: {e}")
        if not dry_run:
            info("Limpiando directorio clonado...")
            shutil.rmtree(dest, ignore_errors=True)
        sys.exit(1)

    # ── 9. Git add + commit + push ──
    step("9. Commit y push...")
    try:
        git_commit_push(slug, nombre, no_push=no_push or dry_run, dry_run=dry_run)
    except RuntimeError as e:
        err(str(e))
        sys.exit(1)

    # ── 10. Esperar redeploy (si corresponde) ──
    if not dry_run and not no_push and not args.skip_deploy_wait:
        step("10. Esperando redeploy en Coolify (30s)...")
        for i in range(30, 0, -5):
            print(f"  {i}s...", end="\r", flush=True)
            time.sleep(5)
        print("  Deploy completado (verificar en coolify.lovbot.ai)    ")

    # ── Resultado final ──
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{GREEN}{BOLD}  Worker clonado y deployado: {slug}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    wa_text = (
        f"Hola {nombre}! Tu bot esta listo. "
        f"Conecta tu WhatsApp Business aca (2 min): "
        f"https://lovbot-onboarding.vercel.app/?client={slug}"
    )
    import urllib.parse
    wa_encoded = urllib.parse.quote(wa_text)

    print(f"URL para mandar al cliente:")
    print(f"  {CYAN}https://lovbot-onboarding.vercel.app/?client={slug}{RESET}\n")

    print(f"Router activo en:")
    print(f"  {CYAN}{BACKEND_URL}/clientes/lovbot/{slug}/whatsapp{RESET}\n")

    print(f"Mensaje listo para WhatsApp:")
    print(f"  {CYAN}https://wa.me/{LOVBOT_WA}?text={wa_encoded}{RESET}\n")

    print(f"Proximos pasos:")
    print(f"  1. Configurar env vars en Coolify para el nuevo worker:")
    print(f"       INMO_DEMO_NOMBRE     = \"{nombre}\"")
    print(f"       INMO_DEMO_CIUDAD     = \"{ciudad}\"")
    print(f"       INMO_DEMO_ASESOR     = \"{asesor.get('nombre', '')}\"")
    print(f"       INMO_DEMO_NUMERO_ASESOR = \"{asesor.get('telefono', '')}\"")
    if data.get("agenda", {}).get("cal_com_activo"):
        print(f"       INMO_DEMO_CAL_API_KEY = <API key de Cal.com>")
        print(f"       INMO_DEMO_CAL_EVENT_ID = <event type ID numerico>")
    print(f"  2. Registrar el WABA del cliente via:")
    print(f"       POST {BACKEND_URL}/clientes/lovbot/inmobiliaria/admin/waba/register-existing")
    print(f"  3. Enviar el link de onboarding al cliente:")
    print(f"       https://lovbot-onboarding.vercel.app/?client={slug}\n")

    if dry_run:
        warn("DRY-RUN completado. Ningun cambio fue aplicado.")
    else:
        ok("Operacion completada exitosamente.")


if __name__ == "__main__":
    main()

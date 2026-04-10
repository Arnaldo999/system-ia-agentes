"""
deploy_service.py — orquesta el deploy completo de un microservicio FastAPI en Coolify.

Uso:
    python execution/deploy_service.py \\
        --name mi-servicio \\
        --description "Descripción del servicio" \\
        --workdir /ruta/al/codigo \\
        --vps arnaldo

Flujo completo:
    1. Crea repo privado en GitHub
    2. Vincula repo a GitHub App de Coolify
    3. Push del código
    4. Crea app en Coolify (red interna, sin FQDN público)
    5. Configura env vars
    6. Dispara deploy
    7. Reporta URL interna + API key para n8n
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(dotenv_path=ROOT / ".env")

from execution.coolify_manager import CoolifyManager
from execution.github_manager import (
    create_private_repo,
    grant_github_app_access,
    initialize_and_push,
)


def deploy(
    name: str,
    description: str,
    workdir: str,
    env_vars: dict | None = None,
    vps: str = "arnaldo",
    with_api_key: bool = True,
) -> dict:
    """
    Deploy completo de un microservicio.

    Args:
        name:         nombre del servicio (también será el repo y el alias Docker)
        description:  descripción para el repo de GitHub
        workdir:      ruta local al código del microservicio
        env_vars:     dict de variables de entorno a inyectar en Coolify
        vps:          "arnaldo" | "robert"
        with_api_key: si True, genera y configura SERVICE_API_KEY automáticamente

    Returns:
        dict con repo_url, app_uuid, alias, service_api_key, internal_url
    """
    print(f"\n{'='*60}")
    print(f"  DEPLOY: {name} → VPS {vps.upper()}")
    print(f"{'='*60}\n")

    manager = CoolifyManager(vps=vps)

    # ── Paso 1: Crear repo privado en GitHub ─────────────────────
    print("[1/5] Creando repo privado en GitHub...")
    owner, repo_name, repo_id = create_private_repo(name, description)

    # ── Paso 2: Vincular repo a GitHub App de Coolify ────────────
    print("[2/5] Vinculando repo a GitHub App de Coolify...")
    github_app = manager.get_github_app()
    grant_github_app_access(repo_id, github_app["installation_id"])

    # ── Paso 3: Push del código ───────────────────────────────────
    print("[3/5] Subiendo código a GitHub...")
    initialize_and_push(
        repo_name=repo_name,
        owner=owner,
        workdir=workdir,
        commit_message=f"Deploy inicial: {name}",
    )

    # ── Paso 4: Crear y configurar app en Coolify ─────────────────
    print("[4/5] Creando app en Coolify...")
    server_uuid = manager.get_server_uuid()
    app = manager.create_application(
        name=name,
        git_repository=f"{owner}/{repo_name}",
        github_app_uuid=github_app["uuid"],
        server_uuid=server_uuid,
    )
    app_uuid = app["uuid"]
    alias = name

    print(f"      Configurando red interna (alias: {alias})...")
    manager.configure_application(app_uuid, alias)

    # ── Paso 5: Configurar env vars + deploy ─────────────────────
    print("[5/5] Configurando variables de entorno y deployando...")
    all_env_vars = dict(env_vars or {})

    service_api_key = None
    if with_api_key:
        service_api_key = secrets.token_hex(32)
        all_env_vars["SERVICE_API_KEY"] = service_api_key

    manager.set_env_vars(app_uuid, all_env_vars)

    deployment = manager.deploy_application(app_uuid)
    deployment_uuid = deployment.get("deployments", [{}])[0].get("deployment_uuid", "")

    # ── Esperar y verificar ───────────────────────────────────────
    if deployment_uuid:
        print(f"\n  Esperando que el deploy termine (90s)...")
        time.sleep(90)
        status_data = manager.get_deployment_status(deployment_uuid)
        status = status_data.get("status", "unknown")
        print(f"  Status: {status}")

    internal_url = f"http://{alias}:8000"
    repo_url = f"https://github.com/{owner}/{repo_name}"

    result = {
        "repo_url": repo_url,
        "app_uuid": app_uuid,
        "alias": alias,
        "internal_url": internal_url,
        "service_api_key": service_api_key,
        "deployment_uuid": deployment_uuid,
    }

    # ── Reporte final ─────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ DEPLOY COMPLETADO")
    print(f"{'='*60}")
    print(f"  Repo:          {repo_url}")
    print(f"  App UUID:      {app_uuid}")
    print(f"  URL interna:   {internal_url}")
    if service_api_key:
        print(f"  X-API-Key:     {service_api_key}")
    print(f"\n  Para n8n — nodo HTTP Request:")
    print(f"    Method:  POST")
    print(f"    URL:     {internal_url}/[endpoint]")
    if service_api_key:
        print(f"    Header:  X-API-Key = {service_api_key}")
    print(f"{'='*60}\n")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy de microservicio en Coolify")
    parser.add_argument("--name", required=True, help="Nombre del servicio")
    parser.add_argument("--description", default="Microservicio System IA")
    parser.add_argument("--workdir", default=".", help="Ruta al código")
    parser.add_argument("--vps", default="arnaldo", choices=["arnaldo", "robert"])
    parser.add_argument("--env-vars", default="{}", help="JSON con vars de entorno extra")
    parser.add_argument("--no-api-key", action="store_true", help="Sin X-API-Key")
    args = parser.parse_args()

    env_vars = json.loads(args.env_vars)
    deploy(
        name=args.name,
        description=args.description,
        workdir=args.workdir,
        env_vars=env_vars,
        vps=args.vps,
        with_api_key=not args.no_api_key,
    )


if __name__ == "__main__":
    main()

"""
github_manager — gestión de repos privados en GitHub y vinculación con Coolify.

Funciones principales:
    create_private_repo()      — crea repo privado (o retorna existente)
    grant_github_app_access()  — vincula el repo a la GitHub App de Coolify
    initialize_and_push()      — init git + commit + push al repo
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN es requerido.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def get_authenticated_user() -> str:
    """Retorna el username del token configurado."""
    response = requests.get(f"{GITHUB_API}/user", headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json()["login"]


def create_private_repo(name: str, description: str) -> tuple[str, str, int]:
    """
    Crea un repo privado en GitHub.
    Si ya existe, retorna sus datos sin error.
    Retorna: (owner, repo_name, repo_id)
    """
    response = requests.post(
        f"{GITHUB_API}/user/repos",
        headers=_headers(),
        json={
            "name": name,
            "private": True,
            "description": description,
            "auto_init": False,
        },
        timeout=30,
    )
    if response.status_code == 422:
        # El repo ya existe — obtener sus datos
        owner = get_authenticated_user()
        existing = requests.get(
            f"{GITHUB_API}/repos/{owner}/{name}",
            headers=_headers(),
            timeout=30,
        )
        existing.raise_for_status()
        payload = existing.json()
        print(f"Repo ya existe: {payload['html_url']}")
        return payload["owner"]["login"], payload["name"], payload["id"]

    response.raise_for_status()
    payload = response.json()
    print(f"Repo creado: {payload['html_url']}")
    return payload["owner"]["login"], payload["name"], payload["id"]


def grant_github_app_access(repo_id: int, installation_id: int) -> None:
    """
    Vincula el repo a la GitHub App de Coolify.
    Requiere que la App tenga scope 'All repositories'.
    """
    response = requests.put(
        f"{GITHUB_API}/user/installations/{installation_id}/repositories/{repo_id}",
        headers=_headers(),
        timeout=30,
    )
    if response.status_code not in {204, 304}:
        response.raise_for_status()
    print(f"Repo vinculado a GitHub App (installation_id={installation_id})")


def initialize_and_push(
    repo_name: str,
    owner: str,
    workdir: str | None = None,
    commit_message: str = "Initial commit",
) -> None:
    """
    Init git (si no existe), commit de todo y push a origin/main.
    workdir: directorio del proyecto a subir (default: cwd)
    """
    path = Path(workdir or Path.cwd())

    if not (path / ".git").exists():
        subprocess.run(["git", "init"], cwd=path, check=True)

    subprocess.run(["git", "add", "."], cwd=path, check=True)

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    if status.stdout.strip():
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=path, check=True,
        )
    else:
        print("Sin cambios para commitear.")

    remote_url = f"https://github.com/{owner}/{repo_name}.git"
    remotes = subprocess.run(
        ["git", "remote"], cwd=path, capture_output=True, text=True, check=True
    ).stdout.splitlines()

    if "origin" not in remotes:
        subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=path, check=True)
    else:
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=path, check=True)

    subprocess.run(["git", "branch", "-M", "main"], cwd=path, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=path, check=True)
    print(f"Código subido a https://github.com/{owner}/{repo_name}")

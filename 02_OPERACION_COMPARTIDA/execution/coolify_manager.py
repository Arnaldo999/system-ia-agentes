"""
CoolifyManager — gestión completa del ciclo de vida de microservicios en Coolify.
Soporta VPS de Arnaldo (Hostinger) y Robert (Hetzner) via variables de entorno.

Uso:
    manager = CoolifyManager()              # VPS Arnaldo (default)
    manager = CoolifyManager(vps="robert")  # VPS Robert
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


@dataclass
class CoolifyManager:
    vps: str = "arnaldo"  # "arnaldo" | "robert"
    base_url: str = field(init=False)
    token: str = field(init=False)
    project_uuid: str = field(init=False)

    def __post_init__(self) -> None:
        if self.vps == "robert":
            self.base_url = os.getenv("COOLIFY_ROBERT_URL", "")
            self.token = os.getenv("COOLIFY_ROBERT_TOKEN", "")
            self.project_uuid = os.getenv("COOLIFY_ROBERT_PROJECT_UUID", "")
        else:
            self.base_url = os.getenv("COOLIFY_URL", "")
            self.token = os.getenv("COOLIFY_TOKEN", "")
            self.project_uuid = os.getenv("COOLIFY_PROJECT_UUID", "")

        self.base_url = self.base_url.rstrip("/")

        if not self.base_url or not self.token or not self.project_uuid:
            raise RuntimeError(
                f"Faltan vars de entorno para VPS '{self.vps}': "
                "COOLIFY_URL, COOLIFY_TOKEN, COOLIFY_PROJECT_UUID"
            )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_server_uuid(self) -> str:
        """Obtiene el UUID del primer servidor disponible."""
        response = requests.get(
            f"{self.base_url}/api/v1/servers",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        servers = response.json()
        if not servers:
            raise RuntimeError("No hay servidores disponibles en Coolify.")
        return servers[0]["uuid"]

    def get_github_app(self) -> dict:
        """Obtiene la GitHub App privada configurada en Coolify."""
        response = requests.get(
            f"{self.base_url}/api/v1/github-apps",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        apps = response.json()
        private_apps = [a for a in apps if not a.get("is_public")]
        if not private_apps:
            raise RuntimeError(
                "No hay GitHub App privada en Coolify. "
                "Configurar en Sources → Add → GitHub App."
            )
        return private_apps[0]

    def create_application(
        self,
        name: str,
        git_repository: str,
        github_app_uuid: str,
        server_uuid: str,
    ) -> dict:
        """Crea una aplicación desde un repo privado de GitHub."""
        payload = {
            "project_uuid": self.project_uuid,
            "server_uuid": server_uuid,
            "environment_name": "production",
            "name": name,
            "git_repository": git_repository,
            "git_branch": "main",
            "github_app_uuid": github_app_uuid,
            "build_pack": "dockerfile",
            "ports_exposes": "8000",
        }
        response = requests.post(
            f"{self.base_url}/api/v1/applications/private-github-app",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def create_postgres_database(self, name: str, server_uuid: str, db_name: str = "appdb") -> dict:
        """Crea una base de datos PostgreSQL interna."""
        payload = {
            "project_uuid": self.project_uuid,
            "server_uuid": server_uuid,
            "environment_name": "production",
            "name": name,
            "postgres_user": "postgres",
            "postgres_password": "postgres",
            "postgres_db": db_name,
            "instant_deploy": True,
        }
        response = requests.post(
            f"{self.base_url}/api/v1/databases/postgresql",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def patch_application(self, app_uuid: str, payload: dict) -> dict:
        """PATCH individual — Coolify rechaza múltiples campos mezclados."""
        response = requests.patch(
            f"{self.base_url}/api/v1/applications/{app_uuid}",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def configure_application(self, app_uuid: str, alias: str) -> None:
        """
        Configura el microservicio como interno:
        - Asigna alias de red Docker (n8n lo alcanza por http://alias:8000)
        - Elimina FQDN público
        - Activa healthcheck en /health
        """
        # Cada PATCH va separado — Coolify rechaza múltiples campos mezclados
        self.patch_application(app_uuid, {"custom_network_aliases": alias})
        self.patch_application(app_uuid, {"domains": ""})
        self.patch_application(app_uuid, {
            "health_check_enabled": True,
            "health_check_path": "/health",
            "health_check_port": 8000,
            "health_check_host": alias,
            "health_check_interval": 10,
            "health_check_timeout": 5,
            "health_check_retries": 10,
            "health_check_start_period": 20,
        })

    def set_env_var(self, app_uuid: str, key: str, value: str) -> dict:
        """Configura una variable de entorno en la app."""
        response = requests.post(
            f"{self.base_url}/api/v1/applications/{app_uuid}/envs",
            headers=self.headers,
            json={"key": key, "value": value, "is_preview": False},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def set_env_vars(self, app_uuid: str, env_vars: dict) -> None:
        """Configura múltiples variables de entorno."""
        for key, value in env_vars.items():
            if value is not None:
                self.set_env_var(app_uuid, key, str(value))

    def deploy_application(self, app_uuid: str) -> dict:
        """Dispara el deploy de la aplicación."""
        response = requests.get(
            f"{self.base_url}/api/v1/deploy",
            headers=self.headers,
            params={"uuid": app_uuid, "force": "true"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def get_application(self, app_uuid: str) -> dict:
        """Obtiene el estado actual de una aplicación."""
        response = requests.get(
            f"{self.base_url}/api/v1/applications/{app_uuid}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_deployment_status(self, deployment_uuid: str) -> dict:
        """Consulta el estado de un deploy en curso."""
        response = requests.get(
            f"{self.base_url}/api/v1/deployments/{deployment_uuid}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

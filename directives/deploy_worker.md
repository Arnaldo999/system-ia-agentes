# Directiva: Deploy Worker FastAPI

**Cuándo usar**: Push de cambios a un worker, deploy inicial de cliente nuevo, hotfix en producción.

## Entradas requeridas

| Campo | Opciones |
|-------|----------|
| `proyecto` | maicol \| prueba \| social \| lovbot-robert \| [nombre custom] |
| `entorno` | arnaldo \| robert \| mica |

Si faltan → preguntar antes de continuar.

## Herramientas

| Script | Propósito |
|--------|-----------|
| `execution/deploy_service.py` | Deploy completo (repo GitHub + Coolify) |
| `execution/coolify_manager.py` | API Coolify para trigger/status |
| `execution/github_manager.py` | Push a repo |

## Flujo

### Paso 1 — Validar sintaxis Python
```bash
cd 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes
python -m py_compile workers/clientes/[proyecto]/worker.py
```
**Si falla → DETENER. No continuar sin resolver el error.**

### Paso 2 — Git push
```bash
git add workers/clientes/[proyecto]/
git commit -m "deploy([proyecto]): [descripción del cambio]"
git push origin master:main
```
Si no hay cambios → saltar al Paso 3.

### Paso 3 — Trigger deploy
```python
python execution/deploy_service.py \
  --name [proyecto] \
  --workdir 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes \
  --vps [entorno]
```

O via curl directo (ver UUIDs en `memory/infraestructura.md`):
```bash
curl -s -X POST "https://coolify.[dominio]/api/v1/deploy?uuid=[UUID]&force=true" \
  -H "Authorization: Bearer $COOLIFY_TOKEN"
```

### Paso 4 — Verificar health (esperar ~30s)

| Entorno | URL |
|---------|-----|
| arnaldo | `https://agentes.arnaldoayalaestratega.cloud/health` |
| robert  | `https://agentes.lovbot.ai/health` |

Respuesta esperada: `{"status": "ok"}`

### Paso 5 — Reportar
```
✅ Deploy [proyecto] → [entorno]
   Commit: [hash]
   Health: ok
```

## Casos límite

- **`maicol`** → advertir que es PRODUCCIÓN LIVE. Pedir confirmación explícita.
- **`render`** → deploy automático con el push. No hay API call adicional.
- **Health no responde** → revisar logs en Coolify UI. Puede ser cold start (~60s).
- **Error 401 Coolify** → token expirado. Ver `memory/infraestructura.md` para renovar.

## Aprendizajes documentados

- Coolify puede tardar hasta 90s en reflejar el nuevo contenedor. No relanzar si el health no responde en los primeros 30s.
- `git push origin master:main` es el formato correcto (local `master` → remoto `main`).

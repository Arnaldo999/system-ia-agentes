# /deploy — Deploy de microservicio en Coolify

Despliega un microservicio FastAPI en Coolify (VPS Arnaldo o Robert).
Crea el repo privado en GitHub, sube el código, configura la red interna Docker y dispara el deploy.

## Uso

```
/deploy
```

Al invocar este comando:

1. Preguntame:
   - **Nombre del servicio** (será el repo y el alias Docker, ej: `maicol-bot`)
   - **Descripción** breve
   - **Ruta al código** (si no es el directorio actual)
   - **VPS destino**: `arnaldo` (Hostinger) o `robert` (Hetzner)
   - **Variables de entorno** que necesita el servicio (las inyecto en Coolify)
   - **¿Con API key?** (recomendado: sí)

2. Verificar que el directorio tiene:
   - `main.py` con `GET /health` retornando `{"status": "ok"}`
   - `Dockerfile`
   - `requirements.txt`
   - `.gitignore` que excluya `.env`

   Si falta alguno, crearlo antes de continuar.

3. Ejecutar el deploy:
   ```bash
   cd /ruta/al/codigo
   python "/home/arna/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL/execution/deploy_service.py" \
     --name NOMBRE \
     --description "DESCRIPCION" \
     --vps arnaldo \
     --env-vars '{"KEY": "value"}'
   ```

4. Entregar al usuario:
   - URL interna: `http://alias:8000`
   - `X-API-Key` generada
   - Configuración del nodo HTTP Request para n8n

## Notas críticas

- El repo siempre es **privado**
- El servicio queda en **red interna Docker** — sin URL pública
- n8n debe estar en el mismo Coolify para alcanzarlo por `http://alias:8000`
- Si el FQDN no se elimina via API: panel → app → Settings → FQDN → borrar → Save
- Scripts en: `execution/coolify_manager.py` y `execution/github_manager.py`

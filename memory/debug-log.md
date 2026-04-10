# Debug y errores frecuentes

## n8n HTTP Request — JSON inválido
- Causa: JSON body pegado como literal o con prefijo incorrecto (por ejemplo "=={{").
- Solucion: usar modo Expression y un prefijo unico "={{...}}".

## Render — "failed to read dockerfile: open Dockerfile: no such file or directory"
- Causa: Render busca el Dockerfile en la raíz del repo, pero el proyecto es un monorepo y el Dockerfile está en un subdirectorio.
- Solución: Configurar `rootDir` en Render vía API o Dashboard → Settings → Build.
  ```bash
  curl -X PATCH "https://api.render.com/v1/services/<SERVICE_ID>" \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"rootDir": "ruta/al/subdirectorio"}'
  ```
- Service ID Maicol: `srv-d6g8qg5m5p6s73a00llg`
- rootDir correcto: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`

## Render — Bot muestra versión vieja del código
- Causa: Render despliega branch `main` pero los commits iban a `master`.
- Solución: `git push origin master:main --force` para sincronizar branches.

## Dockerfile — wget falla en Render free tier
- Causa: `wget` de archivos de fuentes desde GitHub agota timeout en Render free.
- Solución: Eliminar descarga de fuentes Inter; usar solo `fonts-dejavu-core` desde apt (ya incluido en `python:3.11-slim`).

## import time mal ubicado en Python
- Causa: `import time` puesto dentro de un bloque de código (dentro de una función o sección) en lugar del top-level.
- Solución: Todos los imports al inicio del archivo, antes de cualquier código.

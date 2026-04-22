---
description: Revertir el último sync de CRM prod (Mica o Robert) si el smoke test falló
---

# /rollback-crm-prod

Revierte el último commit de tipo `sync(crm-<proyecto>):` del proyecto indicado, volviendo el archivo prod al estado anterior. Útil cuando `/sync-crm-prod` detecta problemas post-deploy.

## Argumento

Usuario debe indicar: **mica** o **robert** (o preguntar si no lo dice).

## Mapeo de archivos

| Proyecto | Archivo PROD que se restaura |
|----------|------------------------------|
| **mica**   | ⚠️ **Modelo único desde 2026-04-22** — no hay prod separado. El archivo editable es `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/crm-v2.html`. Rollback = `git revert` del commit del cambio no deseado. |
| **robert** | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/demo-crm-mvp.html` |

---

## Flujo

### PASO 1 — Confirmar proyecto
Si no se pasa argumento, preguntar "¿Mica o Robert?". NUNCA asumir.

### PASO 2 — Encontrar último commit de sync del proyecto

```bash
git log --oneline --grep="sync(crm-<proyecto>)" -n 1
```

- Si no hay commits de sync → avisar y abortar.
- Si hay → capturar el hash (ej. `a1b2c3d`).

Mostrar al usuario:
- Hash + mensaje del commit a revertir
- Fecha del commit
- Pedir confirmación explícita antes de revertir.

### PASO 3 — Revertir el commit

```bash
git revert <HASH> --no-edit
```

Esto genera un nuevo commit que deshace los cambios (no reescribe historia — más seguro).

### PASO 4 — Push

```bash
git push origin master:main
```

Vercel redeploya solo → prod vuelve a la versión anterior en ~1-2 min.

### PASO 5 — Smoke test post-rollback

Mismos checks que `/sync-crm-prod` paso 7:
- `GET /crm/version` (backend)
- `GET {api_prefix}/crm/leads`
- `GET {api_prefix}/crm/propiedades`

Si todo OK → reportar `"✅ Rollback completo. Prod volvió a vX.Y.Z."`.
Si algo sigue mal → reportar `"⚠️ Rollback aplicado pero <endpoint> aún falla. El problema podría estar en backend/Coolify, no en el HTML."`.

---

## Cuándo usar este comando

- Si el smoke test de `/sync-crm-prod` reportó ❌.
- Si un cliente reporta que el CRM no carga después de un sync reciente.
- Si vos detectás visualmente que prod quedó roto tras sincronizar.

## Cuándo NO usar

- Si el problema NO es del HTML (ej. env var de Coolify, endpoint de backend). Un rollback de HTML no arregla eso — reportar el problema y arreglar en la capa correcta.
- Si ya pasó >24h desde el sync y hubo otros commits encima. Preguntar al usuario antes de revertir.

## Reglas irrompibles

- **NUNCA revertir un commit que NO sea de sync del proyecto indicado.** Confirmar con el mensaje del commit antes de revertir.
- **NUNCA usar `git reset --hard`.** Siempre `git revert` (genera commit nuevo, conserva historia).
- **NUNCA modificar archivos de producción a mano para "arreglar rápido".** Si el rollback no alcanza, volver al flujo dev → sync.

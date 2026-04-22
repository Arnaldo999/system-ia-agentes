---
title: Coolify como default para deploys — no más Vercel por defecto
tags: [infraestructura, deploy, coolify, vercel, regla-operativa]
source_count: 1
proyectos_aplicables: [arnaldo, robert, mica]
proyecto: compartido
---

# Coolify como plataforma default para nuevos deploys

## Regla operativa

Desde el 22 de abril de 2026, **cualquier HTML, sitio web, propuesta, formulario o proyecto estático nuevo se deploya en Coolify (no en Vercel)**.

Vercel queda solo para:
- Apps existentes que ya tienen dominios configurados ahí y mueven volumen (ej: `crm.lovbot.ai` hasta que se migre)
- Casos donde el CDN edge global es crítico (contenido público con tráfico internacional masivo — no es el caso de los proyectos actuales)

## Por qué

### Coolify Hostinger (Arnaldo) ya está corriendo

Tenés un VPS Hostinger con Coolify instalado sirviendo `agentes.arnaldoayalaestratega.cloud` (el backend FastAPI `system-ia-agentes`).

El backend tiene `StaticFiles` mount en `/propuestas/*` que sirve cualquier carpeta dentro de `backends/system-ia-agentes/clientes-publicos/{slug}/`.

### Sin cupos ni límites

| Aspecto | Vercel Free | Coolify Hostinger |
|---------|-------------|-------------------|
| Deploys/día | **100 máx** | **ilimitados** |
| Tiempo build | Limitado | Tu VPS |
| Custom domains | ✅ | ✅ |
| SSL automático | ✅ | ✅ (Let's Encrypt) |
| Auto-deploy git push | ✅ | ✅ |
| Costo | Gratis con límites | Tu VPS (que ya pagás) |

### Fricción histórica con Vercel que se evita

El 21 y 22 de abril de 2026 se agotó el cupo Vercel (100 deploys/día Plan Hobby) varias veces por el ritmo de refactor del CRM Robert. Quedaron 5-6 commits en queue por horas. Se perdió tiempo diagnosticando "¿deployó?" y esperando resets.

En Coolify eso no pasa — cada `git push` se procesa en ~15-30 segundos y no hay límite diario.

## Cómo deployar un HTML/proyecto nuevo en Coolify

### Paso 1 — Crear carpeta y archivos

```bash
# Para contenido cliente-facing (propuestas, briefs, roadmaps):
mkdir -p 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/clientes-publicos/{slug-proyecto}/
cp mi-archivo.html 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/clientes-publicos/{slug-proyecto}/
```

### Paso 2 — Commit + push

```bash
git add -A
git commit -m "feat: {descripción} para {cliente-o-proyecto}"
git push origin master:main
```

### Paso 3 — Esperar 15-30 seg

Coolify detecta el push, redeploya automáticamente.

### Paso 4 — URL resultante

```
https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug-proyecto}/{archivo}.html
```

## Patrón para múltiples Coolify (multi-deploy del mismo repo)

El repo `system-ia-agentes` tiene **2 deployments simultáneos** del mismo código:

| Coolify | Dominio | VPS | Dueño |
|---------|---------|-----|-------|
| **Hostinger Arnaldo** | `agentes.arnaldoayalaestratega.cloud` | Hostinger | Arnaldo |
| **Hetzner Robert** | `agentes.lovbot.ai` | Hetzner | Robert (socio técnico) |

Un solo `git push origin master:main` dispara redeploy en **ambos** en paralelo. Cada uno expone el mismo backend en su propio dominio.

**Implicación práctica**: cualquier archivo nuevo en `clientes-publicos/` automáticamente queda disponible en ambos dominios. Para servirlo SOLO en uno, se puede filtrar por `Host` header en el router FastAPI.

### Para proyecto de Robert específicamente
Los archivos de Robert (CRM v2, landing, docs clientes Lovbot) **conviene ponerlos en carpeta tipo `clientes-publicos/lovbot-*/`** y configurar Coolify Hetzner Robert con su dominio adicional (`crm.lovbot.ai`) apuntando a la app. Así evitamos contaminar la URL de Arnaldo con contenido Lovbot.

## Cuándo SÍ usar Vercel

Casos puntuales:
1. App existente YA productiva con dominio configurado en Vercel (ej: `crm.lovbot.ai`, `system-ia-agencia.vercel.app`) — no migrar sin razón
2. Cliente específico pide explícitamente Vercel por alguna integración
3. Proyecto necesita Edge Functions o CDN global geo-distribuido (no es el caso hoy de ninguno)

## Cuándo migrar un proyecto de Vercel a Coolify

Checklist para migrar:
- [ ] El cliente tiene dominio propio configurable (o acepta usar subdominio)
- [ ] El proyecto no depende de features específicas de Vercel (Edge Functions, ISR, etc)
- [ ] Hay ventana de tiempo para cambio DNS (~5-15 min propagación)
- [ ] Los archivos del proyecto pueden moverse a `clientes-publicos/{slug}/` del monorepo

Si los 4 OK → migrar. Si alguno falla → mantener en Vercel.

## Historial de migración planeada

- **Robert** (`crm.lovbot.ai`): agendada para **23 de abril 2026** después del reset de cupo Vercel de hoy, para que los commits pendientes se deployen primero y después se apague Vercel con todo actualizado.
- **Mica** (`system-ia-agencia.vercel.app`): diferida hasta que Mica compre dominio propio. Sin dominio de ella, no tiene sentido migrar.
- **Clientes nuevos (Cesar, Patricia, futuros)**: **directo a Coolify desde el minuto 1** — ya aplicada esta regla.

## Fuentes

- [[raw/compartido/sesion-2026-04-22-coolify-default]] — sesión donde se tomó la decisión
- [[wiki/entidades/coolify-arnaldo]]
- [[wiki/entidades/coolify-robert]]
- [[wiki/conceptos/onboarding-cliente-nuevo-arnaldo]] — se actualizó para reflejar esta regla

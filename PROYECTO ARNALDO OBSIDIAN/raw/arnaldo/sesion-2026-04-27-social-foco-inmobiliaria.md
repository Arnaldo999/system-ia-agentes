---
title: Sesión Claude 2026-04-27 — Social Worker foco vertical Inmobiliaria (Arnaldo + Mica)
date: 2026-04-27
type: sesion-claude
proyecto: arnaldo
tags: [proyecto-arnaldo, proyecto-mica, social-worker, inmobiliaria, vertical, coolify, env-var]
---

# Sesión 2026-04-27 — Pivote estratégico: vertical inmobiliaria en social automation

## Contexto

Al final de la sesión de CRM Jurídico v2, surgió la decisión estratégica de que Mica y Arnaldo ingresen formalmente a la vertical **Inmobiliarias** con sus cuentas de redes sociales de agencia. El social worker hasta ese momento publicaba contenido genérico (consejos de negocio, testimonios) sin foco de nicho.

**Decisión**: el contenido de redes de las cuentas de *agencia* de Mica y Arnaldo debe posicionarse vendiendo **automatización para inmobiliarias**, con casos de uso, resultados y CTAs al servicio WhatsApp + CRM + Agenda.

## Commit

`5a2f120` — `feat(social): rotación agencia → vertical INMOBILIARIAS + CTA reforzado`

## Cambios técnicos en `workers/social/worker.py`

### Variable de entorno nueva

```python
_AGENCIA_VERTICAL_FOCO = os.environ.get("SOCIAL_AGENCIA_VERTICAL_FOCO", "")
```

Configurable en Coolify sin redeploy (env var + restart).

### Helper de detección de cuenta agencia

```python
def _es_cuenta_agencia(industria: str, publico: str) -> bool:
    palabras = ["agencia", "consultor", "system ia", "lovbot", "automatizacion"]
    combinado = (industria + " " + publico).lower()
    return any(p in combinado for p in palabras)
```

### Diccionario de rotación temática semanal

```python
_ROTACION_TEMAS_AGENCIA_INMOBILIARIA = {
    0: "caso_exito_inmobiliaria",      # Lunes
    1: "objecion_comun_inmobiliaria",  # Martes
    2: "dato_mercado_automatizacion",  # Miércoles
    3: "flujo_bot_inmobiliaria",       # Jueves
    4: "comparacion_con_sin_bot",      # Viernes
    5: "detras_de_escena_agencia",     # Sábado
    6: "pregunta_engancho",            # Domingo
}
```

### Lógica de 3 paths en `_get_tema_del_dia`

1. **Cliente final inmobiliaria** (`industria == "inmobiliaria"`, no es agencia) → tema del cliente (propiedades, inversión).
2. **Cuenta agencia con foco inmobiliaria** (`_es_cuenta_agencia()` + `_AGENCIA_VERTICAL_FOCO == "inmobiliaria"`) → rotación temática agencia.
3. **Default** → tema genérico (consejos empresa, testimonio, etc.).

### Bloque CTA inyectado al prompt

Cuando `es_agencia and foco == "inmobiliaria"`:

```
Bloque CTA obligatorio al final:
"¿Tu inmobiliaria todavía responde consultas a mano? Te mostramos cómo automatizarlo. [Link WhatsApp o Bio]"
(adaptar tono al tema del día)
```

Aplicado tanto a `/social/crear-post` como a `/social/publicar-completo`.

## Env var seteada en Coolify Arnaldo

```
SOCIAL_AGENCIA_VERTICAL_FOCO = inmobiliaria
```

En el servicio `system-ia-agentes` de Coolify Hostinger. Restart aplicado post-set.

## Cómo desactivar

Setear `SOCIAL_AGENCIA_VERTICAL_FOCO = ""` (vacío) en Coolify + Restart. Vuelve al comportamiento genérico sin perder el código.

## Test E2E confirmado

Post generado correctamente con:
- Tema del día según día de semana.
- Énfasis en WhatsApp + Agendamiento + CRM (bloque CTA).
- Tono agencia vendiendo a inmobiliarias (no tono cliente final).

## Decisión estratégica registrada

Arnaldo y Mica acordaron:
1. Usar el social worker para posicionarse en el nicho inmobiliario **antes** de tener casos de éxito públicos.
2. Publicar como agencia que ya resolvió el problema de automatización inmobiliaria.
3. La presencia digital proactiva prepara la audiencia para los primeros prospectos inmobiliarios.

**Pendiente**: avisar a Mica el cambio + instruirla cómo desactivar si no quiere el foco inmobiliaria por ahora.

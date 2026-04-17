# Gastronomía — Estudio de Mercado Sub-nichos
_Generado: 2026-04-04 — Sesión Dream/Research_

## Contexto
Estudio para priorizar sub-nichos del rubro gastronómico y adaptar el `GASTRO_DEMO_SUBNICHE` del worker demo.

---

## Top 5 Sub-nichos Prioritarios (implementados en worker)

| Rank | Sub-niche | Score | Key insight |
|------|-----------|-------|-------------|
| 1 | **Pizzería** | 29/30 | Delivery masivo, ticket medio ~$6.000 ARS, volumen altísimo en LATAM |
| 2 | **Rotisería** | 26/30 | Viandas B2B (empresas) = ticket recurrente predecible |
| 3 | **Menú ejecutivo / Viandas** | 26/30 | 80% del ingreso en horario almuerzo — bot gestiona reserva de vianda |
| 4 | **Hamburguesería** | 25/30 | Público joven, alta adopción digital, combos personalizables |
| 5 | **Sushi** | 23/30 | Ticket alto, delivery premium, clientes frecuentes leales |

> Nota: `sushi` no está en el worker todavía — se puede agregar fácilmente como 6to sub-niche.

---

## Tabla completa — 15 sub-nichos evaluados

| Sub-niche | Potencial WhatsApp | Ops manuales | Ticket prom. (ARS) | Adop. digital | Auto. potencial |
|-----------|-------------------|-------------|-------------------|--------------|----------------|
| Pizzería | Muy alto | Muy alto | 6.000–12.000 | Alta | Muy alto |
| Rotisería | Alto | Alto | 4.000–7.000 | Media | Alto |
| Menú ejecutivo/viandas | Alto | Alto | 3.500–6.000 | Baja | Alto |
| Hamburguesería | Muy alto | Alto | 5.000–10.000 | Alta | Muy alto |
| Sushi | Alto | Muy alto | 8.000–20.000 | Alta | Muy alto |
| Cafetería | Alto | Medio | 1.500–4.500 | Media | Alto |
| Panadería/Pastelería | Medio | Muy alto | 2.000–5.000 | Baja | Medio |
| Heladería | Medio | Bajo | 1.500–3.500 | Media | Medio |
| Parrilla/Asadero | Medio | Medio | 8.000–25.000 | Baja | Medio |
| Dietética/Saludable | Medio | Alto | 4.000–9.000 | Media | Alto |
| Comida árabe | Bajo | Medio | 5.000–12.000 | Baja | Medio |
| Tacos/Mexicana | Bajo | Medio | 4.500–8.000 | Media | Medio |
| Bar/Cervecería | Bajo | Bajo | 6.000–15.000 | Media | Bajo |
| Heladería artesanal | Bajo | Bajo | 2.000–6.000 | Baja | Bajo |
| Empanadas/Regional | Medio | Medio | 2.500–5.500 | Baja | Medio |

---

## Sub-nichos implementados en worker (`GASTRO_DEMO_SUBNICHE`)

```bash
# Valores válidos:
GASTRO_DEMO_SUBNICHE=cafeteria       # default
GASTRO_DEMO_SUBNICHE=pizzeria
GASTRO_DEMO_SUBNICHE=rotiseria
GASTRO_DEMO_SUBNICHE=hamburgueseria
GASTRO_DEMO_SUBNICHE=parrilla
```

Cada sub-niche configura automáticamente:
- Nombre del local (sobreescribible con `GASTRO_DEMO_NOMBRE`)
- Horario de atención
- Alias de pago
- Emoji identificador
- Personalidad del agente (ej: "joven y energética" para hamburguesería)
- Tareas adicionales específicas del sub-niche
- Menú fallback con precios representativos

---

## Argumento de ventas universal

> "Cada vez que tu teléfono está ocupado o no contestás en 3 minutos, el cliente se va a PedidosYa y te cobran 30% de comisión. Nuestro bot atiende en 5 segundos, las 24 horas, sin comisiones."

---

## Próximos sub-nichos a agregar (cuando haya leads)

1. `sushi` — ticket alto, público muy fiel, ideal para demos premium
2. `viandas` — B2B, volumen predecible, diferente al menú ejecutivo (empresa → empresa)
3. `pasteleria` — encargues son el core, similar a cafetería pero foco en repostería

---

## Estrategia de demo para Micaela

- Lead actual: **Luciano** (cafetería) → usar `GASTRO_DEMO_SUBNICHE=cafeteria`
- Demo en Coolify: un deployment por sub-niche con env vars distintas
- CRM HTML: `DEMOS/GASTRONOMIA/gastronomia.html` — conectar via `API_BASE` en localStorage
- Bot simulador incluido en el HTML para mostrar en vivo


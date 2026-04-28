"""
Catálogo de propiedades — wrapper compartido sobre Postgres
============================================================
Wrapper liviano sobre `db_postgres.buscar_propiedades` para que múltiples
canales (WhatsApp, voz, web) consulten el mismo catálogo sin duplicar SQL.

BD: `lovbot_crm_modelo` (Coolify Hetzner). Para clientes nuevos se duplica
con `crear-db-cliente` y este módulo respeta el env `LOVBOT_PG_DB`.

Devuelve formato simplificado (claves snake_case) optimizado para que el
agente de voz lo lea sin transformaciones extra.
"""

from typing import Optional


def search_properties(
    tipo: Optional[str] = None,
    operacion: Optional[str] = None,
    zona: Optional[str] = None,
    presupuesto: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Busca propiedades en `lovbot_crm_modelo`.

    Args:
        tipo: "casa" | "departamento" | "lote" | "ph" | etc.
        operacion: "venta" | "alquiler"
        zona: nombre exacto de zona (ej: "Posadas Centro")
        presupuesto: "hata_50k" | "50k_100k" | "100k_200k" | "mas_200k"
        limit: máximo a retornar

    Returns:
        lista de {"titulo", "tipo", "operacion", "zona", "precio", "moneda",
                  "dormitorios", "banios", "direccion", "imagen", "maps"}
    """
    from workers.demos.inmobiliaria import db_postgres as db
    raw = db.buscar_propiedades(
        tipo=tipo, operacion=operacion, zona=zona,
        presupuesto=presupuesto, limit=limit,
    )
    return [
        {
            "titulo": p.get("Titulo", ""),
            "descripcion": p.get("Descripcion", ""),
            "tipo": p.get("Tipo", ""),
            "operacion": p.get("Operacion", ""),
            "zona": p.get("Zona", ""),
            "precio": p.get("Precio"),
            "moneda": p.get("Moneda", "USD"),
            "presupuesto": p.get("Presupuesto", ""),
            "disponible": p.get("Disponible", ""),
            "dormitorios": p.get("Dormitorios"),
            "banios": p.get("Banios"),
            "metros_cubiertos": p.get("Metros_Cubiertos"),
            "metros_terreno": p.get("Metros_Terreno"),
            "direccion": p.get("Direccion", ""),
            "imagen": p.get("Imagen", ""),
            "maps": p.get("Maps", ""),
        }
        for p in raw
    ]


def format_property_for_voice(prop: dict) -> str:
    """Convierte una propiedad a frase natural para que el agente la lea.

    Mantenerlo corto: voz no tolera párrafos largos.
    """
    partes = []
    if prop.get("titulo"):
        partes.append(prop["titulo"])
    if prop.get("dormitorios"):
        partes.append(f"{prop['dormitorios']} dormitorios")
    if prop.get("zona"):
        partes.append(f"en {prop['zona']}")
    precio = prop.get("precio")
    moneda = prop.get("moneda", "USD")
    if precio:
        partes.append(f"a {moneda} {int(precio):,}".replace(",", "."))
    return ", ".join(partes) if partes else "propiedad sin datos"

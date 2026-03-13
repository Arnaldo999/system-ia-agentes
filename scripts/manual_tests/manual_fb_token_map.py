import os
import requests as req
from dotenv import load_dotenv

load_dotenv("system-ia-agentes/.env")

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "YOUR_META_ACCESS_TOKEN")

def _build_page_token_map() -> dict:
    """Construye mapa {page_id: token} desde env vars. Cliente principal + CLIENT_N_*"""
    mapa = {}
    
    # Valores de fallback de prueba si no existen en el entorno, pero sin tokens hardcodeados.
    os.environ.setdefault("FACEBOOK_PAGE_ID", os.getenv("FACEBOOK_PAGE_ID", "TEST_FB_PAGE_ID"))
    os.environ.setdefault("IG_BUSINESS_ACCOUNT_ID", os.getenv("IG_BUSINESS_ACCOUNT_ID", "TEST_IG_ID"))
    os.environ.setdefault("META_ACCESS_TOKEN", META_ACCESS_TOKEN)
    
    os.environ.setdefault("CLIENT_2_PAGE_ID", os.getenv("CLIENT_2_PAGE_ID", "TEST_C2_FB_ID"))
    os.environ.setdefault("CLIENT_2_IG_ID", os.getenv("CLIENT_2_IG_ID", "TEST_C2_IG_ID"))
    os.environ.setdefault("CLIENT_2_META_TOKEN", os.getenv("CLIENT_2_META_TOKEN", "TEST_C2_TOKEN"))

    for pid in [os.environ.get("FACEBOOK_PAGE_ID", ""), os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")]:
        if pid:
            mapa[pid] = os.environ.get("META_ACCESS_TOKEN", "")
            
    for i in range(2, 50):
        page_id = os.environ.get(f"CLIENT_{i}_PAGE_ID", "")
        ig_id   = os.environ.get(f"CLIENT_{i}_IG_ID", "")
        token   = os.environ.get(f"CLIENT_{i}_META_TOKEN", "")
        if not page_id and not ig_id:
            continue
        if page_id:
            mapa[page_id] = token
        if ig_id:
            mapa[ig_id] = token
    return mapa

print("Map:", _build_page_token_map())

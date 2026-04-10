import requests
import json
import os
from dotenv import load_dotenv

load_dotenv("system-ia-agentes/.env")

airtable_base = os.getenv("AIRTABLE_BASE_ID", "YOUR_AIRTABLE_BASE_ID")
airtable_pat = os.getenv("AIRTABLE_PAT", "YOUR_AIRTABLE_PAT")
test_phone = os.getenv("TEST_PHONE", "12345678")

url = f"https://api.airtable.com/v0/{airtable_base}/conversaciones_activas"
headers = {"Authorization": f"Bearer {airtable_pat}"}
r = requests.get(url, headers=headers, params={"filterByFormula": f"{{telefono}}='{test_phone}'", "maxRecords": 1})
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

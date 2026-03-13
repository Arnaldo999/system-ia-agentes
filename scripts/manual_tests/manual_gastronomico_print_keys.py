import urllib.request
import json
req = urllib.request.Request("https://system-ia-agentes.onrender.com/gastronomico/debug/schema")
r = urllib.request.urlopen(req)
data = json.loads(r.read().decode('utf-8'))
for c in data.get('Conversaciones', {}).get('records', []):
    print(c['fields'].keys())

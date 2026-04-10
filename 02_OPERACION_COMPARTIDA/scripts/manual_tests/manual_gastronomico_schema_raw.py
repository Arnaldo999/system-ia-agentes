import urllib.request
import json
req = urllib.request.Request("https://system-ia-agentes.onrender.com/gastronomico/debug/schema")
r = urllib.request.urlopen(req)
print(r.read().decode('utf-8'))

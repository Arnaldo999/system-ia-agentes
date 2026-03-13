const fs = require('fs');
const https = require('https');
const path = require('path');

const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5MmI5ZDg4Ny0zMTgzLTQ2YjEtOWRiNC1jMzhiNTRlZjJjYjYiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODExYzlhMTYtNWJiOS00MGNjLTgwYzktNmE3ZTc3OGIxYjNjIiwiaWF0IjoxNzcyNDQ4MDIzfQ.jHNTu63Iyg7R-oH-IG6Q5Pl1SPFNpEXt9_iEPJ6_l10';
const baseUrl = 'https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/api/v1/workflows';
const repoPath = '/home/arna/PROYECTOS SYSTEM IA/INGENIERO N8N/N8N-REPOSITORIO-SYSTEM-IA-DEMO';

const files = fs.readdirSync(repoPath).filter(f => f.endsWith('.json'));

async function importWorkflow(fileName) {
  const filePath = path.join(repoPath, fileName);
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));

  // the API expects specific settings object, or no settings. We will pass an empty object or minimal allowed settings.
  const payload = JSON.stringify({
    name: data.name,
    nodes: data.nodes,
    connections: data.connections,
    settings: {}
  });

  const options = {
    method: 'POST',
    headers: {
      'X-N8N-API-KEY': apiKey,
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }
  };

  return new Promise((resolve, reject) => {
    const req = https.request(baseUrl, options, (res) => {
      let responseBody = '';
      res.on('data', chunk => responseBody += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          console.log(`✅ Success importing: ${fileName}`);
          resolve(responseBody);
        } else {
          console.error(`❌ Failed import: ${fileName} - ${res.statusCode} ${responseBody}`);
          resolve(null);
        }
      });
    });

    req.on('error', (e) => {
      console.error(`❌ Error on request for ${fileName}: ${e.message}`);
      reject(e);
    });

    req.write(payload);
    req.end();
  });
}

async function main() {
  const skipList = [
    'automatizar-redes-sociales-.json',
    'tienda-de-ropa-whatsapp-—-patrón-conecta-🎯 Demos.json',
    '🍷-restaurante---flujo-principal-🎯 Demos.json',
    '🎛️-maestro---router-de-demos-🎛️ MAESTRO.json',
    '🏥-clínica-salud-total-—-agendamiento-ia-con-cal.com-AGENDAMIENTOS DE CITAS.json'
  ];

  for (const file of files) {
    if (!skipList.includes(file)) {
      await importWorkflow(file);
      await new Promise(r => setTimeout(r, 1000));
    }
  }
}

main();

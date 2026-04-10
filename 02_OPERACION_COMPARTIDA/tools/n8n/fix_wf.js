const https = require('https');

const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZDAzODMwMC1mNDJmLTQ3NzQtODhhOC00YmFkZjI0NTk1N2IiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODhjMjM4MDQtMzE1My00ZTRhLWIyZDAtMTkwMmI1YzhmMWQyIiwiaWF0IjoxNzcyMTQ4MDMzfQ.EOmMTQqZtbppYtVztUzWgfafM_mS9JE4s1OJcGD-JTg';
const baseUrl = 'https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/api/v1/workflows/EMLA9zVV5g5Vae8G';

const options = {
  method: 'GET',
  headers: {
    'X-N8N-API-KEY': apiKey,
    'Accept': 'application/json'
  }
};

https.get(baseUrl, options, (res) => {
  let body = '';
  res.on('data', chunk => body += chunk);
  res.on('end', () => {
    const wf = JSON.parse(body);
    const node = wf.nodes.find(n => n.name === 'Procesar Datos y Calcular Puntaje' || n.name.includes('Procesar Datos'));
    if (node) {
      let code = node.parameters.jsCode;

      if (!code.includes("if (!mHor) delete props['Disponibilidad Horario'];")) {
        code = code.replace(
          "const notionBody = { parent: { database_id:",
          "if (!mHor || mHor === 'No especificado') delete props['Disponibilidad Horario'];\nif (!mDia || mDia === 'No especificado') delete props['Disponibilidad D\u00eda'];\nconst notionBody = { parent: { database_id:"
        );
      }

      const payload = {
        name: wf.name,
        nodes: wf.nodes,
        connections: wf.connections,
        settings: {}
      };
      payload.nodes = payload.nodes.map(n => {
        if (n.name === node.name) {
          n.parameters.jsCode = code;
        }
        return n;
      });

      const putOptions = {
        method: 'PUT',
        headers: {
          'X-N8N-API-KEY': apiKey,
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      };
      const req = https.request(baseUrl, putOptions, (res2) => {
        let body2 = '';
        res2.on('data', c => body2 += c);
        res2.on('end', () => console.log('UPDATE STATUS:', res2.statusCode, body2));
      });
      req.write(JSON.stringify(payload));
      req.end();
    }
  });
});

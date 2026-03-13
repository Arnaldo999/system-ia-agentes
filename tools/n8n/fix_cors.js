const https = require('https');
const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZDAzODMwMC1mNDJmLTQ3NzQtODhhOC00YmFkZjI0NTk1N2IiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODhjMjM4MDQtMzE1My00ZTRhLWIyZDAtMTkwMmI1YzhmMWQyIiwiaWF0IjoxNzcyMTQ4MDMzfQ.EOmMTQqZtbppYtVztUzWgfafM_mS9JE4s1OJcGD-JTg';
const baseUrl = 'https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/api/v1/workflows/yp2YGpEwdCUfL9xP';

const options = { method: 'GET', headers: { 'X-N8N-API-KEY': apiKey, 'Accept': 'application/json' } };
https.get(baseUrl, options, (res) => {
  let body = '';
  res.on('data', chunk => body += chunk);
  res.on('end', () => {
    const wf = JSON.parse(body);
    const node = wf.nodes.find(n => n.name === '📋 Webhook Formulario');
    if (node) {
      // Enable CORS on the Webhook node
      node.parameters.options = node.parameters.options || {};
      node.parameters.options.responseHeaders = {
        entries: [
          { name: 'Access-Control-Allow-Origin', value: '*' },
          { name: 'Access-Control-Allow-Methods', value: '*' },
          { name: 'Access-Control-Allow-Headers', value: '*' }
        ]
      };
      // For earlier versions, sometimes it's under something else, but CORS is usually:
      node.parameters.options.ignoreAuthentication = true; 
      
      const payload = {
        name: wf.name,
        nodes: wf.nodes,
        connections: wf.connections,
        settings: {}
      };
      
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
        res2.on('end', () => console.log('UPDATE STATUS:', res2.statusCode));
      });
      req.write(JSON.stringify(payload));
      req.end();
    } else {
      console.log('Webhook node not found');
    }
  });
});

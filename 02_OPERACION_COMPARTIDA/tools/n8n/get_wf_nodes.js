const https = require('https');
const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZDAzODMwMC1mNDJmLTQ3NzQtODhhOC00YmFkZjI0NTk1N2IiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODhjMjM4MDQtMzE1My00ZTRhLWIyZDAtMTkwMmI1YzhmMWQyIiwiaWF0IjoxNzcyMTQ4MDMzfQ.EOmMTQqZtbppYtVztUzWgfafM_mS9JE4s1OJcGD-JTg';
const baseUrl = 'https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/api/v1/workflows/yp2YGpEwdCUfL9xP';

const options = { method: 'GET', headers: { 'X-N8N-API-KEY': apiKey, 'Accept': 'application/json' } };
https.get(baseUrl, options, (res) => {
    let body = '';
    res.on('data', chunk => body += chunk);
    res.on('end', () => {
        const wf = JSON.parse(body);
        console.log("ALL NODES:");
        wf.nodes.forEach(n => {
            console.log("-", n.name, "(", n.type, ")");
            if (n.type.includes('notion')) {
                console.log("NOTION:", JSON.stringify(n.parameters, null, 2));
            }
        });
    });
});

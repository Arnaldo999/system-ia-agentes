const fs = require('fs');
const https = require('https');

const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZDAzODMwMC1mNDJmLTQ3NzQtODhhOC00YmFkZjI0NTk1N2IiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODhjMjM4MDQtMzE1My00ZTRhLWIyZDAtMTkwMmI1YzhmMWQyIiwiaWF0IjoxNzcyMTQ4MDMzfQ.EOmMTQqZtbppYtVztUzWgfafM_mS9JE4s1OJcGD-JTg';
const baseUrl = 'https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/api/v1/workflows';

const options = {
  method: 'GET',
  headers: {
    'X-N8N-API-KEY': apiKey,
    'Accept': 'application/json'
  }
};

const req = https.request(baseUrl, options, (res) => {
  let responseBody = '';
  res.on('data', chunk => responseBody += chunk);
  res.on('end', () => {
    const data = JSON.parse(responseBody);
    console.log(JSON.stringify(data.data.filter(w => w.name.toLowerCase().includes('lead')), null, 2));
  });
});

req.on('error', (e) => {
  console.error(e);
});

req.end();

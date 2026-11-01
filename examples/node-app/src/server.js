'use strict';

const http = require('node:http');
const { slugify } = require('./slug');

function handler(req, res) {
  const url = new URL(req.url, 'http://localhost');
  const send = (status, body) => {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(body));
  };

  if (req.method === 'GET' && url.pathname === '/health') return send(200, { status: 'ok' });
  if (req.method === 'GET' && url.pathname === '/slug') {
    const text = url.searchParams.get('text');
    if (!text) return send(400, { error: 'El parámetro text es obligatorio' });
    return send(200, { text, slug: slugify(text) });
  }
  return send(404, { error: 'No encontrado' });
}

if (require.main === module) {
  const port = Number(process.env.PORT ?? 3000);
  http.createServer(handler).listen(port, () => console.log(`Escuchando en :${port}`));
}

module.exports = { handler };

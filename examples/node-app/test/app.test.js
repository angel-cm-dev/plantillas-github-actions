'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { slugify } = require('../src/slug');
const { handler } = require('../src/server');

test('slugify elimina tildes y símbolos', () => {
  assert.equal(slugify('  Hola, Señor Pérez! '), 'hola-senor-perez');
  assert.equal(slugify('Ñandú & Cía.'), 'nandu-cia');
  assert.equal(slugify(''), '');
});

test('endpoints /health y /slug', async (t) => {
  const server = http.createServer(handler).listen(0);
  t.after(() => server.close());
  const base = `http://127.0.0.1:${server.address().port}`;

  const health = await fetch(`${base}/health`);
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { status: 'ok' });

  const slug = await fetch(`${base}/slug?text=Lima%20Per%C3%BA`);
  assert.deepEqual(await slug.json(), { text: 'Lima Perú', slug: 'lima-peru' });

  assert.equal((await fetch(`${base}/slug`)).status, 400);
  assert.equal((await fetch(`${base}/nada`)).status, 404);
});

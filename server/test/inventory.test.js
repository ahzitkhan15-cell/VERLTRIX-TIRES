import assert from 'node:assert/strict';
import { once } from 'node:events';
import test from 'node:test';
import { createApp } from '../src/app.js';

const VALID_ITEM = {
  name: 'Michelin Pilot Sport 4',
  sku: 'MPS4-245-40-18',
  category: 'Performance',
  quantity: 12,
};

async function startServer(t) {
  const server = createApp().listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));
  return `http://127.0.0.1:${server.address().port}`;
}

async function postItem(baseUrl, payload) {
  const response = await fetch(`${baseUrl}/api/inventory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return { status: response.status, body: await response.json() };
}

async function getItems(baseUrl) {
  const response = await fetch(`${baseUrl}/api/inventory`);
  return response.json();
}

test('POST /api/inventory creates an item', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, VALID_ITEM);

  assert.equal(status, 201);
  assert.equal(body.item.name, VALID_ITEM.name);
  assert.equal(body.item.sku, VALID_ITEM.sku);
  assert.equal(body.item.category, VALID_ITEM.category);
  assert.equal(body.item.quantity, VALID_ITEM.quantity);
  assert.equal(body.item.status, 'In stock');
  assert.equal(typeof body.item.id, 'string');
  assert.ok(body.item.id.length > 0);
  assert.ok(!Number.isNaN(Date.parse(body.item.createdAt)));
});

test('POST /api/inventory makes the item available to GET', async (t) => {
  const baseUrl = await startServer(t);

  await postItem(baseUrl, VALID_ITEM);
  await postItem(baseUrl, { name: 'Pirelli P Zero', sku: 'PZ-225-45-17', quantity: 4 });

  const { items, count } = await getItems(baseUrl);

  assert.equal(count, 2);
  assert.deepEqual(
    items.map((item) => item.sku),
    ['MPS4-245-40-18', 'PZ-225-45-17'],
  );
});

test('POST /api/inventory derives stock status from quantity', async (t) => {
  const baseUrl = await startServer(t);

  const cases = [
    { quantity: 0, expected: 'Out of stock' },
    { quantity: 5, expected: 'Low stock' },
    { quantity: 10, expected: 'In stock' },
  ];

  for (const { quantity, expected } of cases) {
    const { status, body } = await postItem(baseUrl, {
      name: `Tire ${quantity}`,
      sku: `QTY-${quantity}`,
      quantity,
    });

    assert.equal(status, 201);
    assert.equal(body.item.status, expected);
  }
});

test('POST /api/inventory trims input and defaults the category', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, {
    name: '  Bridgestone Blizzak  ',
    sku: '  BZ-205-55-16  ',
    quantity: 3,
  });

  assert.equal(status, 201);
  assert.equal(body.item.name, 'Bridgestone Blizzak');
  assert.equal(body.item.sku, 'BZ-205-55-16');
  assert.equal(body.item.category, 'Uncategorized');
});

test('POST /api/inventory floors fractional quantities', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, {
    name: 'Yokohama Advan',
    sku: 'YA-235-40-18',
    quantity: 3.9,
  });

  assert.equal(status, 201);
  assert.equal(body.item.quantity, 3);
});

test('POST /api/inventory reports a floored fraction as out of stock', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, {
    name: 'Nokian Hakkapeliitta',
    sku: 'NH-205-55-16',
    quantity: 0.5,
  });

  assert.equal(status, 201);
  assert.equal(body.item.quantity, 0);
  assert.equal(body.item.status, 'Out of stock');
});

test('POST /api/inventory rejects quantities that are not numbers', async (t) => {
  const baseUrl = await startServer(t);

  for (const quantity of [true, '', [], {}]) {
    const { status, body } = await postItem(baseUrl, {
      name: 'Bad quantity type',
      sku: `BAD-TYPE-${JSON.stringify(quantity)}`,
      quantity,
    });

    assert.equal(status, 400, `expected 400 for quantity ${JSON.stringify(quantity)}`);
    assert.equal(body.error, 'Quantity must be zero or greater.');
  }
});

test('POST /api/inventory rejects a missing name', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, { sku: 'NO-NAME', quantity: 1 });

  assert.equal(status, 400);
  assert.equal(body.error, 'Name and SKU are required.');
});

test('POST /api/inventory rejects a missing SKU', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, { name: 'No SKU', quantity: 1 });

  assert.equal(status, 400);
  assert.equal(body.error, 'Name and SKU are required.');
});

test('POST /api/inventory rejects a blank name', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, {
    name: '   ',
    sku: 'BLANK-NAME',
    quantity: 1,
  });

  assert.equal(status, 400);
  assert.equal(body.error, 'Name and SKU are required.');
});

test('POST /api/inventory rejects an empty body', async (t) => {
  const baseUrl = await startServer(t);

  const { status } = await postItem(baseUrl, {});

  assert.equal(status, 400);
});

test('POST /api/inventory rejects a negative quantity', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, {
    name: 'Negative stock',
    sku: 'NEG-1',
    quantity: -1,
  });

  assert.equal(status, 400);
  assert.equal(body.error, 'Quantity must be zero or greater.');
});

test('POST /api/inventory rejects a non-numeric quantity', async (t) => {
  const baseUrl = await startServer(t);

  const { status, body } = await postItem(baseUrl, {
    name: 'Bad quantity',
    sku: 'BAD-QTY',
    quantity: 'not-a-number',
  });

  assert.equal(status, 400);
  assert.equal(body.error, 'Quantity must be zero or greater.');
});

test('unknown API paths return a JSON 404', async (t) => {
  const baseUrl = await startServer(t);

  const response = await fetch(`${baseUrl}/api/inventory/missing`);

  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: 'Not found.' });
});

test('POST /api/inventory rejects duplicate SKUs regardless of case', async (t) => {
  const baseUrl = await startServer(t);

  await postItem(baseUrl, VALID_ITEM);
  const { status, body } = await postItem(baseUrl, {
    name: 'Same SKU, different case',
    sku: 'mps4-245-40-18',
    quantity: 1,
  });

  assert.equal(status, 409);
  assert.equal(body.error, 'An item with this SKU already exists.');

  const { count } = await getItems(baseUrl);
  assert.equal(count, 1);
});

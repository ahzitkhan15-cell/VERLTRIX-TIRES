import { randomUUID } from 'node:crypto';
import { Router } from 'express';

function stockStatus(quantity) {
  if (quantity === 0) return 'Out of stock';
  if (quantity < 10) return 'Low stock';
  return 'In stock';
}

// Accepts a number, or a numeric string from a form post, but not values whose
// Number() coercion would invent a count (true -> 1, [] -> 0, '' -> 0).
function parseQuantity(value) {
  if (value === undefined || value === null) return 0;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && value.trim() !== '') return Number(value);
  return Number.NaN;
}

// Placeholder in-memory store. Replace this with the real inventory data layer
// (database models, validation, stock movements) as features are built.
// A router owns its own store so each createApp() is isolated (see tests).
export default function createInventoryRouter() {
  const items = [];
  const router = Router();

  router.get('/', (_req, res) => {
    res.json({ items, count: items.length });
  });

  router.post('/', (req, res) => {
    const { name, sku, category, quantity } = req.body ?? {};

    const itemName = typeof name === 'string' ? name.trim() : '';
    const itemSku = typeof sku === 'string' ? sku.trim() : '';
    const itemCategory = typeof category === 'string' ? category.trim() : '';
    const rawQuantity = parseQuantity(quantity);

    if (!itemName || !itemSku) {
      return res.status(400).json({ error: 'Name and SKU are required.' });
    }

    if (!Number.isFinite(rawQuantity) || rawQuantity < 0) {
      return res.status(400).json({ error: 'Quantity must be zero or greater.' });
    }

    // Floor once, so the stored count and the derived status agree.
    const itemQuantity = Math.floor(rawQuantity);

    const duplicate = items.some(
      (item) => item.sku.toLowerCase() === itemSku.toLowerCase(),
    );
    if (duplicate) {
      return res
        .status(409)
        .json({ error: 'An item with this SKU already exists.' });
    }

    const item = {
      id: randomUUID(),
      name: itemName,
      sku: itemSku,
      category: itemCategory || 'Uncategorized',
      quantity: itemQuantity,
      status: stockStatus(itemQuantity),
      createdAt: new Date().toISOString(),
    };

    items.push(item);
    res.status(201).json({ item });
  });

  return router;
}

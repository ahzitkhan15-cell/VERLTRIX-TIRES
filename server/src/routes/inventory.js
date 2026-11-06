import { randomUUID } from 'node:crypto';
import { Router } from 'express';

// Placeholder in-memory store. Replace this with the real inventory data layer
// (database models, validation, stock movements) as features are built.
const items = [];

function stockStatus(quantity) {
  if (quantity === 0) return 'Out of stock';
  if (quantity < 10) return 'Low stock';
  return 'In stock';
}

const router = Router();

router.get('/', (_req, res) => {
  res.json({ items, count: items.length });
});

router.post('/', (req, res) => {
  const { name, sku, category, quantity } = req.body ?? {};

  const itemName = typeof name === 'string' ? name.trim() : '';
  const itemSku = typeof sku === 'string' ? sku.trim() : '';
  const itemCategory = typeof category === 'string' ? category.trim() : '';
  const itemQuantity = Number(quantity ?? 0);

  if (!itemName || !itemSku) {
    return res.status(400).json({ error: 'Name and SKU are required.' });
  }

  if (!Number.isFinite(itemQuantity) || itemQuantity < 0) {
    return res.status(400).json({ error: 'Quantity must be zero or greater.' });
  }

  const duplicate = items.some(
    (item) => item.sku.toLowerCase() === itemSku.toLowerCase(),
  );
  if (duplicate) {
    return res.status(409).json({ error: 'An item with this SKU already exists.' });
  }

  const item = {
    id: randomUUID(),
    name: itemName,
    sku: itemSku,
    category: itemCategory || 'Uncategorized',
    quantity: Math.floor(itemQuantity),
    status: stockStatus(itemQuantity),
    createdAt: new Date().toISOString(),
  };

  items.push(item);
  res.status(201).json({ item });
});

export default router;

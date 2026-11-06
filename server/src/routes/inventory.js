import { Router } from 'express';

// Placeholder in-memory store. Replace this with the real inventory data layer
// (database models, validation, stock movements) as features are built.
const items = [];

const router = Router();

router.get('/', (_req, res) => {
  res.json({ items, count: items.length });
});

export default router;

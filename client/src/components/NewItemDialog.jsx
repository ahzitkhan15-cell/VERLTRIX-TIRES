import { useEffect, useRef, useState } from 'react';

const EMPTY_FORM = { name: '', sku: '', category: '', quantity: '0' };

export default function NewItemDialog({ open, onClose, onCreated }) {
  const dialogRef = useRef(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      setForm(EMPTY_FORM);
      setError('');
      setSaving(false);
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  function update(field) {
    return (event) => {
      setForm((current) => ({ ...current, [field]: event.target.value }));
    };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');

    try {
      const response = await fetch('/api/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          sku: form.sku,
          category: form.category,
          quantity: Number(form.quantity),
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || 'Could not save the item.');
      }

      onCreated(payload.item);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog className="dialog" ref={dialogRef} onCancel={onClose} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="dialog__head">
          <h2>New inventory item</h2>
          <p>Add a tire to the stock list.</p>
        </div>

        <div className="dialog__body">
          <div className="field">
            <label htmlFor="item-name">Item name</label>
            <input
              id="item-name"
              name="name"
              value={form.name}
              onChange={update('name')}
              placeholder="e.g. Michelin Pilot Sport 4"
              autoComplete="off"
              required
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="item-sku">SKU</label>
              <input
                id="item-sku"
                name="sku"
                value={form.sku}
                onChange={update('sku')}
                placeholder="MPS4-245-40-18"
                autoComplete="off"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="item-category">Category</label>
              <input
                id="item-category"
                name="category"
                value={form.category}
                onChange={update('category')}
                placeholder="Performance"
                autoComplete="off"
              />
            </div>
          </div>

          <div className="field field--narrow">
            <label htmlFor="item-quantity">Quantity on hand</label>
            <input
              id="item-quantity"
              name="quantity"
              type="number"
              min="0"
              step="1"
              value={form.quantity}
              onChange={update('quantity')}
              required
            />
          </div>

          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>

        <div className="dialog__foot">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={saving}>
            {saving ? 'Adding…' : 'Add item'}
          </button>
        </div>
      </form>
    </dialog>
  );
}

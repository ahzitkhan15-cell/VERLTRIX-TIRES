# VERLTRIX-TIRES
INVENTORY

## Feed fixer

`feed_fixer.py` fills the gaps reported in the feed fix list and re-validates the feed.
It needs only Python 3.9+ (standard library).

`data/feed_fix_list.csv` is the current fix list: 4,027 rows, 4,005 failing.
- 3,938 rows need **price** and **availability**
- 874 rows need an **image_link**
- 45 TIRELINK rows need both an **image_link** and a **link** (product URL)

### 1. Make a sheet to fill in

```bash
python3 feed_fixer.py template data/feed_fix_list.csv -o out/to_fill.csv
```

This writes only the failing rows, with empty `price`, `availability`, `image_link`, `link` columns.

### 2. Merge your data and re-validate

```bash
python3 feed_fixer.py fix data/feed_fix_list.csv prices.csv images.csv \
    --feed-out out/feed_fixed.csv --report-out out/feed_fix_list_remaining.csv
```

- Source files are matched on `record_id` (also accepted: `id`, `sku`, `item_id`, `offer_id`).
- Column aliases are accepted, e.g. `selling_price`, `stock`, `image_url`, `product_url`.
- When several files supply the same field, the later file wins. Empty cells never overwrite.
- Prices are normalised to `129.99 USD` (`--currency` sets the default for bare numbers).
- Availability accepts `in_stock` / `out_of_stock` / `preorder` / `backorder`, common phrases
  ("In Stock", "sold out"), or a stock count (`>0` = in stock).
- `image_link` and `link` must be `http(s)://` URLs with a host name.
- By default a row is checked only on the fields it originally failed. Use `--require-all`
  to require every field on every row. A value a source *does* supply is always validated,
  even for a field that passed before, so a bad value never ends up in the feed update.

`feed_fixed.csv` is an update sheet, not a complete feed: it holds the values your source
files supplied. A blank cell means "not changed by this run", so keep the value already in
your live feed (the fix list doesn't contain those values). Upload it as a supplemental
feed, or use `--require-all` with complete source files to get a full feed.

The report has the same columns as the input fix list, so you can run it again on the remaining rows.
The command exits with code 1 while any row still fails.

### Tests

```bash
python3 -m unittest discover -s tests
```

#!/usr/bin/env python3
"""Fill the gaps in the tire product feed and re-validate it.

Takes the feed fix list (record_id,title,status,failing_fields,what_is_needed)
plus one or more source files that hold the missing values, merges them by
record_id, and writes:

  * a feed update:  record_id,title,price,availability,image_link,link
    (only values supplied by the sources; a blank cell means "not changed by
    this run, keep the value already in the live feed")
  * a new fix list in the same format as the input, listing what is still wrong

Usage:
  # 1. Make a fill-in sheet with only the failing rows and the columns they need
  python3 feed_fixer.py template data/feed_fix_list.csv -o out/to_fill.csv

  # 2. Merge one or more source files (later files win on conflicts)
  python3 feed_fixer.py fix data/feed_fix_list.csv prices.csv images.csv \
      --feed-out out/feed_fixed.csv --report-out out/feed_fix_list_remaining.csv

Source files are CSVs with a record_id column (aliases: id, sku, item_id) and
any of: price, availability, image_link, link (aliases listed in COLUMN_ALIASES).
Only the Python standard library is used.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = ["price", "availability", "image_link", "link"]

COLUMN_ALIASES = {
    "record_id": ["record_id", "id", "sku", "item_id", "offer_id"],
    "price": ["price", "sale_price", "selling_price", "retail_price"],
    "availability": ["availability", "stock", "stock_status", "inventory_status"],
    "image_link": ["image_link", "image", "image_url", "img"],
    "link": ["link", "url", "product_url", "product_link"],
}

NEEDED_MSG = {
    "price": "Supply a selling price for this row",
    "availability": "Supply a stock/availability status for this row",
    "image_link": "Supply an image URL for this row",
    "link": "Supply a product URL for this row",
}

AVAILABILITY_VALUES = {"in_stock", "out_of_stock", "preorder", "backorder"}
AVAILABILITY_ALIASES = {
    "in stock": "in_stock", "instock": "in_stock", "available": "in_stock",
    "yes": "in_stock", "true": "in_stock",
    "out of stock": "out_of_stock", "outofstock": "out_of_stock",
    "sold out": "out_of_stock", "unavailable": "out_of_stock",
    "no": "out_of_stock", "false": "out_of_stock",
    "pre-order": "preorder", "pre order": "preorder",
    "back order": "backorder", "back-order": "backorder",
}

DEFAULT_CURRENCY = "USD"
# Commas are only allowed as thousands separators (1,049.00), so 12,34 is rejected.
PRICE_RE = re.compile(r"^\s*\$?\s*((?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?)"
                      r"\s*([A-Za-z]{3})?\s*$")
URL_RE = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Normalisation / validation. Each returns (normalised_value, error_or_None).
# --------------------------------------------------------------------------- #
def normalize_price(raw: str, currency: str = DEFAULT_CURRENCY):
    """Return a price as '129.99 USD', or an error for blank, unreadable or <= 0."""
    raw = (raw or "").strip()
    if not raw:
        return "", "missing"
    m = PRICE_RE.match(raw)
    if not m:
        return raw, f"unreadable price '{raw}' (expected e.g. 129.99 or 129.99 USD)"
    amount = float(m.group(1).replace(",", ""))
    if amount <= 0:
        return raw, f"price must be greater than 0 (got '{raw}')"
    return f"{amount:.2f} {(m.group(2) or currency).upper()}", None


def normalize_availability(raw: str, *, numeric_stock: bool = True):
    """Map a stock status or stock count onto one of AVAILABILITY_VALUES."""
    raw = (raw or "").strip()
    if not raw:
        return "", "missing"
    key = raw.lower().replace("_", " ").strip()
    if key.replace(" ", "_") in AVAILABILITY_VALUES:
        return key.replace(" ", "_"), None
    if key in AVAILABILITY_ALIASES:
        return AVAILABILITY_ALIASES[key], None
    if numeric_stock and re.fullmatch(r"-?\d+", key):
        return ("in_stock" if int(key) > 0 else "out_of_stock"), None
    return raw, (f"unknown availability '{raw}' "
                 f"(use one of {', '.join(sorted(AVAILABILITY_VALUES))} or a stock count)")


def normalize_url(raw: str):
    """Accept only absolute http(s) URLs."""
    raw = (raw or "").strip()
    if not raw:
        return "", "missing"
    if not URL_RE.match(raw) or not _has_valid_authority(raw):
        return raw, f"not a valid http(s) URL '{raw}'"
    return raw, None


def _has_valid_authority(url: str) -> bool:
    """True if the URL has a host name and, if given, a numeric port."""
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises ValueError for a non-numeric or out-of-range port
    except ValueError:  # also covers malformed IPv6 literals like [not-an-ip]
        return False
    return bool(parts.hostname)


def normalize(field: str, raw: str, currency: str):
    """Dispatch to the normaliser for the given feed field."""
    if field == "price":
        return normalize_price(raw, currency)
    if field == "availability":
        return normalize_availability(raw)
    return normalize_url(raw)


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #
def read_csv(path: Path) -> list[dict]:
    """Read a CSV (BOM-tolerant) into a list of dicts."""
    return read_csv_with_header(path)[1]


def read_csv_with_header(path: Path) -> tuple[list[str], list[dict]]:
    """Read a CSV, returning its header even when it has no data rows."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    """Write rows to a CSV, creating parent folders and ignoring extra keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def resolve_columns(header: list[str], path: Path) -> dict[str, str]:
    """Map canonical field name -> actual column name in a source file."""
    lowered = {h.strip().lower(): h for h in header if h}
    mapping = {}
    for canon, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in lowered:
                mapping[canon] = lowered[a]
                break
    if "record_id" not in mapping:
        raise SystemExit(f"{path}: no record_id column (looked for {COLUMN_ALIASES['record_id']})")
    if len(mapping) == 1:
        raise SystemExit(f"{path}: no usable columns; expected any of {FIELDS}")
    return mapping


def load_sources(paths: list[Path]) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Merge source files; later files override earlier ones for non-empty values."""
    merged: dict[str, dict[str, str]] = {}
    notes = []
    for p in paths:
        header, rows = read_csv_with_header(p)
        cols = resolve_columns(header, p)
        used = [c for c in FIELDS if c in cols]
        notes.append(f"{p}: {len(rows)} rows, fields {', '.join(used)}")
        for row in rows:
            rid = (row.get(cols["record_id"]) or "").strip()
            if not rid:
                continue
            target = merged.setdefault(rid, {})
            for field in used:
                val = (row.get(cols[field]) or "").strip()
                if val:
                    target[field] = val
    return merged, notes


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def failing_fields(row: dict) -> list[str]:
    """Split the ';'-separated failing_fields column into a list."""
    return [f.strip() for f in (row.get("failing_fields") or "").split(";") if f.strip()]


def _fix_row(row: dict, src: dict[str, str], currency: str, require_all: bool):
    """Merge one row with its source values. Returns (feed_row, problems, filled)."""
    failed = failing_fields(row)
    check = FIELDS if require_all else failed
    out = {"record_id": row["record_id"].strip(), "title": row.get("title", "")}
    problems, filled = [], 0
    for field in FIELDS:
        raw = src.get(field, "")
        if field not in check and not raw:
            continue  # passed upstream, nothing supplied, leave untouched
        value, err = normalize(field, raw, currency)
        out[field] = value
        if err is None:
            filled += field in failed
        elif field in check or raw:
            problems.append((field, NEEDED_MSG[field] if err == "missing" else err))
    return out, problems, filled


def fix(fix_rows: list[dict], sources: dict[str, dict[str, str]], currency: str,
        require_all: bool = False):
    """Return (feed_rows, report_rows, stats).

    By default a row is only checked on the fields it failed originally (the
    others already passed upstream). With require_all every field must be
    present in the sources, which is what you want when building a full feed.
    """
    feed, report = [], []
    stats = {"rows": 0, "pass": 0, "fail": 0, "unmatched": 0, "filled": 0}
    for row in fix_rows:
        stats["rows"] += 1
        src = sources.get(row["record_id"].strip())
        if src is None and failing_fields(row):
            stats["unmatched"] += 1
        out, problems, filled = _fix_row(row, src or {}, currency, require_all)
        stats["filled"] += filled
        stats["fail" if problems else "pass"] += 1
        feed.append(out)
        report.append({
            "record_id": out["record_id"],
            "title": out["title"],
            "status": "FAIL" if problems else "PASS",
            "failing_fields": "; ".join(f for f, _ in problems),
            "what_is_needed": "; ".join(f"{f}: {m}" for f, m in problems),
        })
    return feed, report, stats


def make_template(fix_rows: list[dict]) -> tuple[list[str], list[dict]]:
    """Build a fill-in sheet: failing rows only, with just the columns they need."""
    needed = [f for f in FIELDS if any(f in failing_fields(r) for r in fix_rows)]
    rows = [
        {"record_id": r["record_id"], "title": r.get("title", ""),
         **{f: "" for f in needed}}
        for r in fix_rows if failing_fields(r)
    ]
    return ["record_id", "title", *needed], rows


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the template and fix commands."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="write a fill-in sheet for the failing rows")
    t.add_argument("fix_list", type=Path)
    t.add_argument("-o", "--out", type=Path, default=Path("out/to_fill.csv"))

    f = sub.add_parser("fix", help="merge source files into the feed and re-validate")
    f.add_argument("fix_list", type=Path)
    f.add_argument("sources", type=Path, nargs="+")
    f.add_argument("--feed-out", type=Path, default=Path("out/feed_fixed.csv"))
    f.add_argument("--report-out", type=Path,
                   default=Path("out/feed_fix_list_remaining.csv"))
    f.add_argument("--currency", default=DEFAULT_CURRENCY,
                   help="currency for bare prices (default USD)")
    f.add_argument("--require-all", action="store_true",
                   help="require every field, not just the ones that failed originally")
    return ap


def run_fix(args: argparse.Namespace, fix_rows: list[dict]) -> int:
    """Run the fix command; exit code 1 if any row still fails."""
    sources, notes = load_sources(args.sources)
    for n in notes:
        print(n)
    feed, report, s = fix(fix_rows, sources, args.currency, args.require_all)
    write_csv(args.feed_out, ["record_id", "title", *FIELDS], feed)
    write_csv(args.report_out,
              ["record_id", "title", "status", "failing_fields", "what_is_needed"], report)
    print(f"{s['rows']} rows: {s['pass']} PASS, {s['fail']} FAIL "
          f"({s['unmatched']} failing rows had no match in any source); "
          f"{s['filled']} missing values filled")
    print(f"Feed:   {args.feed_out}\nReport: {args.report_out}")
    return 1 if s["fail"] else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the command line."""
    args = build_parser().parse_args(argv)
    fix_rows = read_csv(args.fix_list)
    missing = {"record_id", "failing_fields"} - set(fix_rows[0].keys() if fix_rows else [])
    if missing:
        raise SystemExit(f"{args.fix_list}: missing columns {sorted(missing)}")

    if args.cmd == "template":
        header, rows = make_template(fix_rows)
        write_csv(args.out, header, rows)
        print(f"Wrote {len(rows)} rows needing {', '.join(header[2:])} to {args.out}")
        return 0
    return run_fix(args, fix_rows)


if __name__ == "__main__":
    sys.exit(main())

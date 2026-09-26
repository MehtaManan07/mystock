# Per-item GST on invoices

Goal: stop averaging/blending tax across an invoice. Every line item carries its own
GST rate (and HSN), the PDF shows a rate-wise breakup, and totals reconcile exactly
with the source data.

Driver: Deodap/Dabster weekly sheet SM53 mixes 18% and 5% lines. SALE-0041 was issued
with a blended 7.64%+7.64%, which is not filing-accurate.

## Phase 1 — Data model

- [x] 1.1 Add `gst_rate` (Numeric(5,2), nullable) to `Product` — master default GST %
- [x] 1.2 Add `hsn_code` (String(20), nullable) to `Product` — per-product HSN, falls back to company setting
- [x] 1.3 Add `tax_rate` (Numeric(5,2), nullable) to `TransactionItem` — rate frozen at sale time
- [x] 1.4 Add `tax_amount` (Numeric(15,2), nullable) to `TransactionItem` — tax frozen at sale time
- [x] 1.5 Alembic migration for 1.1–1.4 (all nullable, additive only)

## Phase 2 — Schemas

- [x] 2.1 `TransactionItemCreate.tax_rate` optional (percent, 0–100)
- [x] 2.2 `CreateProductDto` / `UpdateProductDto` accept `gst_rate` + `hsn_code`
- [x] 2.3 `ProductResponse` exposes `gst_rate` + `hsn_code`
- [x] 2.4 Transaction item response exposes `tax_rate` + `tax_amount`

## Phase 3 — Service (create_sale / create_purchase)

- [x] 3.1 Resolve per-line rate: explicit `item.tax_rate` -> `product.gst_rate` -> none
- [x] 3.2 When any line resolves a rate: line tax = round(line_total * rate/100, 2); transaction tax = sum of lines
- [x] 3.3 Legacy fallback: no line rates -> keep caller's `tax_amount`, back-fill line snapshots pro-rata
- [x] 3.4 Persist `tax_rate` + `tax_amount` on every transaction item

## Phase 4 — Invoice PDF

- [x] 4.1 Drop blended `igst_rate = tax_amount / subtotal` derivation
- [x] 4.2 Line totals use the item's own tax
- [x] 4.3 Per-line HSN from product, fallback to company settings
- [x] 4.4 Summary shows one CGST/SGST (or IGST) pair per distinct rate, not an average
- [x] 4.5 Items-table Total row = sum of line totals (stop showing the rounded-up grand total)
- [x] 4.6 Add "Round Off" line so Taxable + Tax + RoundOff = Total on the face of the invoice

## Phase 5 — Verify

- [x] 5.1 Extend `scripts/preview_invoice.py` to take per-item `tax_rate` (render without touching DB)
- [x] 5.2 Render SM53 preview, assert every line + rate-wise subtotal matches the Excel to the paisa
- [x] 5.3 Regression: render a single-rate invoice, confirm output is unchanged vs today
- [x] 5.4 Unit-check `_calculate_line_taxes`: explicit rates, product-master rates, line
      overrides product, partial rates, legacy pro-rata (sums exactly), zero tax,
      rounding remainder, explicit 0% (exempt) — 8/8 pass

## Phase 6 — Apply to real data (needs explicit go-ahead)

- [x] 6.1 Run migration against Turso prod
- [x] 6.2 Backfill `gst_rate` + `hsn_code` for the 18 SM53 products from the sheet
- [x] 6.3 Backfill SALE-0041 line tax + recompute transaction tax
- [x] 6.4 Regenerate SALE-0041 PDF, re-verify against Excel

## Open questions

- RESOLVED: keep the `math.ceil` round-up (4152.34 -> 4153.00) with a "Round Off" row.
- UI (`CreateSalePage`) still has a single invoice-level "GST %" field. Backend now
  supports per-line rates; the UI needs a follow-up to expose it.
- RESOLVED (for now): HSN `44219` stored as-is. Still looks truncated (HSN should be
  4/6/8 digits) - confirm with Deodap and update `product.hsn_code` for products
  318/319/320 if it should be 44219999 or 4421.

---

# Round 2 — HSN fix, per-line rates in UI, SM54 bill

## Phase 7 — HSN correction

- [x] 7.1 Update `hsn_code` 44219 -> 44219999 on products 318, 319, 320

## Phase 8 — UI per-line GST rates

- [x] 8.1 Add per-line GST % input to CreateSalePage line items
- [x] 8.2 Default each line from the product's `gst_rate`
- [x] 8.3 Compute tax per line; show rate-wise breakup in the totals panel
- [x] 8.4 Send `tax_rate` per item in the create-sale payload
- [x] 8.5 Same treatment for CreatePurchasePage

## Phase 9 — SM54 bill (Deodap/Dabster, 24.08.26–30.08.26)

- [x] 9.1 Parse SM54; Main <-> detail reconciled (31 SKUs, 298 qty, 11222 taxable)
- [x] 9.2 Cancelled order #239-27783471 correctly excluded from both sheets
- [x] 9.3 Credit note 239-0000014 explains the qty gap on 73340
      (13 shipped - 8 returned = 5). Main is authoritative.
- [x] 9.4 Map all 31 vendor SKUs -> products; create any missing
- [x] 9.5 Set gst_rate + hsn_code on every product in this bill
- [x] 9.6 Ensure stock exists for each line
- [x] 9.7 SALE-0042 created; totals 11222 / 1550.27 / 12773 - match sheet exactly
- [x] 9.8 PDF generated (2 pages); all 31 lines reconcile to the paisa

## SM54 notes

- 31 line items, 298 qty, taxable 11222.00, tax 1550.27, total 12772.27
- Rate mix: 18% on 7609.00, 5% on 3613.00
- A cancelled order (SKU 73305, qty 2, 300.00) is excluded - do NOT bill it
- Credit note of 151.04 already netted off inside the Main sheet quantities

## Phase 7b - bugs found while doing the above

- [x] `ProductService.create` / `bulk_create` silently dropped `gst_rate` + `hsn_code`
      (DTO accepted them, response exposed them, service never passed them to the model)
- [x] Invoice table bolded the last row of EVERY page, not just the grand-total row
- [x] Page breaks used a hardcoded 20/35 rows instead of measuring; page 1 wasted
      a third of its height. Now packs by measured fit and reserves exact footer space.
- [x] Long invoice numbers overlapped the "Dated:" label in the header

---

# Round 3 — Re-issue SM53 bill (17.08.26–23.08.26), dated 23-Aug-2026

## Phase 10 — Parse & verify source

- [x] 10.1 Confirm `...SM53 (1).xlsx` is byte-identical to `...SM53.xlsx` (same md5)
- [x] 10.2 Parse Main + detail sheets; Main <-> detail fully reconciled
      (18 SKUs, 106 qty, taxable 3602.00, tax 550.34, total 4152.34)
- [x] 10.3 No cancelled orders in the detail sheet for this period
- [x] 10.4 Rate mix: 18% on 2848.00, 5% on 754.00

## Phase 11 — Identify bills to delete

- [x] 11.1 Only ONE live SM53 bill exists: SALE-0041 (id 41, dated 2026-08-23, 4153.00)
- [x] 11.2 SALE-0040 (2026-08-18) is the SM52 bill — do NOT touch
- [x] 11.3 No soft-deleted SM53 duplicates
- [x] 11.4 Deleted SALE-0041 via API (soft delete at 2026-09-09 05:13:35 UTC)
- [x] 11.5 Balance -4153.00 and stock restored on all 18 lines, verified vs snapshot

## Phase 12 — Generate fresh bill

- [x] 12.1 All 18 SKUs mapped; every gst_rate matches the sheet
- [x] 12.2 Stock available on every line
- [x] 12.3 SALE-0043 (id 43) created, dated 2026-08-23
- [x] 12.4 PDF generated (1 page); client timed out at 300s but the upload succeeded
- [x] 12.5 All 18 lines reconciled; 3602 / 550.34 / 4153
- [x] 12.6 PDF visually checked - slabs, round off, words and totals all correct

## Notes

- New bill will be numbered SALE-0043 (numbering takes max id, and SALE-0042/SM54
  already exists). The 0041 gap is a cancelled invoice — flag for GST filing.

## Round 3 result

- SALE-0041 soft-deleted; SALE-0043 issued in its place, dated 23-Aug-2026.
- Net effect on contact 1 balance and on stock is exactly zero vs the pre-delete snapshot.
- Snapshot of the deleted bill kept at /tmp/sm53/snapshot_41.json (also preserved in the
  session workspace) in case SALE-0041 ever needs restoring.
- `invoice/generate` takes >5 min for an 18-line bill and blew the 300s client timeout,
  even though the GCS upload succeeded. Worth making that endpoint async or faster.

---

# Round 4 — SM55 bill (31.08.26–06.09.26), dated 06-Sep-2026

## Phase 13 — Parse & verify source

- [x] 13.1 No existing bill for this period — nothing to delete
- [x] 13.2 Main sheet column layout differs from SM53/SM54 (one fewer leading blank
      column). Parser is now header-driven, not positional.
- [x] 13.3 17 SKUs, 42 qty, taxable 1942.00; no cancelled orders (all 27 rows Dispatched)
- [x] 13.4 CONFLICT: SKU 73363 laxmi_charan_paduka_sticker — Main tab says 18%,
      all 5 detail rows say 5%. Resolved to 5%: detail rows are the real invoices
      (#R-2627-08-*), SM53 billed it at 5%, product 318 is 5% in the DB, and its
      same-HSN sibling 73365 is 5%. Parser now treats the detail tab as
      authoritative on rate and reports any override it applies.
- [x] 13.5 Effect: tax 318.10 -> 280.92, total 2260.10 -> 2222.92 (ceil 2223).
      Our bill will NOT tie to Deodap's Main-tab total — flag the typo to them.

## Phase 14 — Generate bill

- [x] 14.1 All 17 SKUs mapped (322–330 already created during SM54); stock OK
- [x] 14.2 SALE-0044 (id 44) created, dated 2026-09-06
- [x] 14.3 All 17 lines reconciled; 1942 / 280.92 / 2223
- [x] 14.4 PDF generated and visually checked

## Phase 15 — Invoice layout bug (found during 14.4)

- [x] 15.1 17-line bill rendered with page 1 ~30% empty and a single orphan row
      plus the totals stranded on page 2
- [x] 15.2 Root cause A: `rows_that_fit = min(rows_that_fit, remaining - 1)` forced a
      row onto the next page even when every row fitted and only the footer did not
- [x] 15.3 Root cause B: only the signature block could overflow to a new page; the
      totals box itself had no overflow guard
- [x] 15.4 Fix: keep all remaining rows + grand-total row together when they fit, and
      give the whole footer block its own page when it does not fit below the table
- [x] 15.5 Regression: SALE-0043 (18 lines) still 1 page, SALE-0042 (31 lines) still
      2 pages with the same layout as before
- [x] 15.6 SALE-0044 regenerated on the fixed renderer

## Round 4 result

- SALE-0044 issued, dated 06-Sep-2026, total 2223.00.
- `invoice_generator.py` gained the pagination fix (uncommitted, with the rest).

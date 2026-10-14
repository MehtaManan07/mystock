# GST reporting

This backend module reads **Transactions** and **PDF Bills** from SQL. It produces
a reconciliation JSON report and GSTR-1 Excel interchange workbook without
changing stock, balances, payments, issued PDFs or source invoice amounts.
It does **not** submit a GST return, certify tax classifications, or validate
recipient registration status against the GST portal.

## Rollout

Code and migration `0016_gst_reporting` require local review and explicit
deployment/migration approval. Back up the database before upgrading from `0015`.
Install the pinned `openpyxl` dependency through the existing requirements file.
Apply the migration **before deploying this code**: new sale creation and PDF
registration now capture a reporting snapshot in the same database transaction.
No historical records are backfilled automatically.

`gst_reviews` is an append-only table of snapshots and reviewed revisions,
identified by source key and revision. Source keys are `transaction:<id>`,
`pdf_invoice:<id>` and `additional:<caller-key>`. Reporting-only additional records
represent genuine missing sales/bills of supply or supplier-issued credit/debit
notes, not fabricated adjustments to make a return balance.

Future source snapshots capture the buyer, available HSN, quantities, prices,
tax rates and tax amounts at creation. They are initially **unverified**:
place of supply, UQC, invoice type, reverse-charge status and document series
need explicit review. A missing GSTIN does not establish exemption. Product
packing names such as `1x10` do not multiply billed quantities.

Historical transaction HSN/rates that are not stored are left missing. They must
be established from original documents. Today's product tax settings are not
used to reconstruct historical invoices. Snapshots are not automatically changed
when the product/contact master changes. A later accounting-data change makes
the associated review stale; it cannot silently pass export.
Both the reviewed `document` and current `source_document` are available for
comparison. A captured invoice moved outside its reviewed period, or physically
removed, remains a blocker rather than silently disappearing from that report.

## APIs

All endpoints require an authenticated **ADMIN or STAFF**. JSON responses use
the normal API success envelope; the Excel download is binary, not JSON-wrapped.

| Endpoint | Purpose |
|---|---|
| `POST /api/gst-reports/reconcile` | Read both registers and return documents, grouped totals and blockers |
| `GET /api/gst-reports/sources/{kind}/{id}` | Load an invoice automatically, its fingerprint and latest review |
| `PUT /api/gst-reports/sources/{kind}/{id}` | Append a verified review of that automatically loaded document |
| `POST /api/gst-reports/documents` | Append a reporting-only additional document/revision |
| `GET /api/gst-reports/history/{source_key}` | Read the complete snapshot/review history |
| `POST /api/gst-reports/export` | Recompute and download a reconciled Excel workbook |

`kind` is `transaction` or `pdf_invoice`. Do not manually recreate existing
invoices in `documents`; review their source key instead. A source review cannot
change its number, date, amounts, existing line prices/quantities/taxes or tax
type. It may complete missing reporting details with evidence. Reporting errors
that require changing the issued invoice must use the separate approved
correction workflow.

Review input contains `expected_revision`, `expected_source_sha256`,
`document` (the loaded document with verified additions), `disposition`, and an
`evidence` description/reference. `disposition` is `include`, `cancelled`,
`not_issued`, or `duplicate`. Every exclusion remains visible with its original
value in the reconciliation. Deletion alone does not prove a legal cancellation.
Use `not_issued` for an actual unissued draft, not to omit a taxable sale.

Additional document input contains a stable caller-generated `key`,
`expected_revision` (zero for first creation), `document`, `disposition`, and
`evidence`. Credit/debit notes use positive original amounts; the report subtracts
credit notes and adds debit notes. Supply `original_invoice_number` and
`original_invoice_date`; unregistered notes also require
`original_invoice_value` for B2CL/B2CS classification. Note dates determine the
reporting period; references to previous-period invoices do not move the note.
Record a supplier-issued GST credit note, not an assumed credit from a customer's
order cancellation or a settlement adjustment already netted elsewhere.

Writes use optimistic revisions; exact retries are idempotent. Concurrent
different revisions return `409`. Old revisions are not overwritten or deleted.

## Reconciliation request

```json
{
  "from_date": "2026-07-01",
  "to_date": "2026-09-30",
  "filing_frequency": "quarterly",
  "preceding_year_turnover_above_5cr": false,
  "sources_complete": false,
  "no_iff_or_previously_filed_records": false,
  "no_unsupported_supplies_or_amendments": false,
  "cross_period_and_cancellations_reviewed": false,
  "gstin_hsn_and_uqc_verified": false,
  "document_series_complete": false
}
```

Use a completed calendar month or GST quarter, May 2025 or later. The booleans
are explicit accountant/user attestations. Leave them false until established;
the report still explains what is missing, but export is blocked. In particular,
the absence of additional documents in SQL does not prove source completeness.
Invoices already furnished in IFF must not be uploaded again. This version
blocks such periods rather than subtracting unverified previously-filed amounts.

Each line has `line_key`, `description`, `quantity`, optional `unit_price`,
`taxable_value`, `tax_rate`, `tax_amount`, `hsn`, `uqc` and `treatment`.
Treatment is `taxable`, `nil_rated`, `exempt`, `non_gst` or unresolved `unknown`.
Despite its name, `taxable_value` is the line's pre-tax value for all treatments;
the report separates taxable, exempt, nil-rated and non-GST turnover.
Zero-rate/unknown lines are not automatically classified.

Document `cgst`, `sgst`, `igst` and `rate_taxes` preserve the original billed
component split. Decimal arithmetic checks line values, rate taxes, header totals
and sub-rupee rounding. Rate buckets must match the exact billed total, including
any one-paise CGST/SGST difference. Missing or inconsistent data is a blocker.

Groups are by recipient GSTIN, invoice type, place of supply, document kind,
treatment and GST rate. Report totals are net of included credit/debit notes.
Group amounts exclude invoice-level rounding; rounding and gross invoice values
are only shown in document/report totals, not misleadingly assigned to a rate.
`source_invoice_total = included_document_total + excluded_document_total`
must hold for a reconciled report. It includes reporting-only documents and signed
notes as well as both registers. Current SQL values are compared with reviewed
values; a nonzero `source_reconciliation_difference` is an explicit blocker.
Unknown lines are not silently included in a taxable/exempt category; unresolved
classification produces a reconciliation difference and blocks export.

Document series are explicit. Within a series, numeric serials must be unique,
have the same prefix/suffix, and have no unexplained gap among the period's
documents. Genuine cancelled serials must be represented and reviewed. The
completeness attestation also covers leading/trailing missing serials that cannot
be discovered from the available rows.

## Excel output and scope

Send `{"report": <same request>, "expected_report_sha256": "<reviewed digest>"}`
to `/export`. A changed report returns `409`; unresolved blockers return `422`.
The digest includes the reviewed inputs and a fiscal-year source/review digest. Export
is recalculated from SQL, not trusted from client-supplied totals.

The workbook uses the column names/order of the supplied TallyPrime GSTR-1
export, including the separate `hsn(b2b)` / `hsn(b2c)` sheets. No invoice data
from the April-June sample is embedded in the module.

- `b2b,sez,de`: regular registered invoices, one row per GST rate; full invoice
  value repeats across rate rows and must **not** be summed per row.
- `b2cl`: interstate unregistered invoices **above Rs100,000**; `b2cs` groups
  the remaining unregistered sales by place of supply and rate.
- `cdnr` / `cdnur`: supplier-issued registered/B2CL notes; B2CS notes net into
  B2CS. Exempt/nil/non-GST values net into `exemp`.
- HSN summaries aggregate HSN, UQC and rate, separating registered/unregistered
  supplies. Tax is allocated in paise to HSN groups with deterministic largest
  remainders, preserving billed component totals. Non-GST values are only in
  `exemp`; HSN Total Value excludes invoice round-off, which stays in the report.
- `docs`: issued/cancelled counts by explicit document series and kind.

Supported UQCs: `NOS`, `PCS`, `SET`, `PAC`, `BOX`, `CTN`, `KGS`, `GMS`, `MTR`,
`SQM`, `LTR`, `OTH`, and `NA` for services. Other units block this version's
workbook instead of being silently converted. Supported GST rates are explicit
in `reporting.py`; unfamiliar rates block export rather than being coerced.
Negative net B2CS/HSN/exemption amounts require period-specific guidance and block
export. These layout restrictions are also blockers in the reconciliation JSON.

**Not supported in this version:** exports, SEZ/deemed exports, ECO tables
14/15, advances, amendments, prior IFF/return reconciliation, cess,
invoice-level discounts, and unregistered reverse-charge supplies.
Unsupported template sheets are blank only after the explicit scope attestation.
Do not use that attestation if any such supply actually applies.

The workbook is **not directly uploadable to the GST portal**. Import and validate
it with the current official Returns Offline Tool, resolve its errors, generate
JSON, and reconcile the portal preview before filing. Tool/portal acceptance has
not been certified by these local checks. Some tool versions do not import
`exemp` and `docs`; verify/enter those totals in the portal separately.
The module never signs, submits, marks filed, or pays a return.

Official references:
- [GST Portal GSTR-1 manual](https://tutorial.gst.gov.in/userguide/returns/Creation_of_Outward_Supplies_Return_in_GSTR-1.htm):
  B2CL threshold from August 2024, HSN B2B/B2C split from May 2025, notes and documents.
- [GST Portal IFF FAQ](https://tutorial.gst.gov.in/userguide/returns/FAQs_IFF.htm):
  invoices furnished in IFF are not entered again in the quarterly return.

## Offline verification

`tests/test_gst_reports.py` uses in-memory SQLite, guarded network DB access and
mocked API services. Cases cover arithmetic, classifications, registration
snapshots, revisions, collisions, notes, date changes, grouping,
Excel round trips and access control. Existing PDF-register tests also cover
the new snapshot hook. Run only after explicit permission:

```bash
venv/bin/python -m unittest discover -s tests -p 'test_gst_reports.py'
venv/bin/python -m unittest discover -s tests -p 'test_pdf_invoices.py'
```

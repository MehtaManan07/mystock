# PDF Bills

The **PDF Bills** screen archives standalone issued invoices alongside (not inside)
the existing Transactions workflow. It does not change inventory, contacts,
customer balances or payments. Regular transaction PDFs remain in Transactions.

## Rollout gate

The existing PDF Bills backend/frontend and migration
`0014_pdf_invoice_register` are live. Historical imports have been performed with
approval. Do not perform additional imports, commits or deployment without approval.
The newer company-bank-details code and date-added list ordering described below
are **not yet deployed**.

For another environment, after approval, back up the database and apply migration
`0014_pdf_invoice_register` (parent: `0013_per_item_gst`), then deploy backend and
frontend. The backend requires this table even for normal sales because sale
number generation skips numbers reserved by standalone invoices. Do not start
the new backend against a database without this migration.
Apply the reviewed Nginx `client_max_body_size 12m` setting as well (10 MiB PDF
plus multipart metadata); the deployment template includes it for HTTP and HTTPS.

The frontend's existing API base points to production. Do not use it for local
upload experimentation. Static checks do not issue HTTP requests.

## UI and API

All authenticated roles can search/filter the register and view/download PDFs.
The list sorts by date added (`created_at`), newest first, with descending record
ID breaking timestamp ties across pages. Printed invoice dates do not affect
this order; the From/To date filters still apply to the printed invoice date.
ADMIN and STAFF can upload an issued PDF (maximum 10 MiB) and enter the printed
invoice details. Copy amounts exactly: taxable + CGST + SGST + IGST + round-off
must equal the final total. IGST cannot be combined with CGST/SGST. Round-off must
be less than one rupee in either direction.

Amounts use decimal arithmetic. The upload checks file signatures and arithmetic,
**not whether the entered metadata matches the PDF contents**. Verify the original
before importing. Records and archived PDFs are immutable; there is no edit or
delete action in this initial version.

Authenticated endpoints (under `/api`):

| Endpoint | Purpose |
|---|---|
| `GET /pdf-invoices` | Paginated search, `from_date`, `to_date`, `page`, `page_size` |
| `GET /pdf-invoices/{id}` | Stored metadata and upload status |
| `GET /pdf-invoices/{id}/file` | Checksum-verified PDF, proxied through the API |
| `POST /pdf-invoices` | Multipart `metadata` (JSON string) and `file` (original PDF) |

Metadata is stored in Turso `pdf_invoices`. Objects are stored in the existing
bucket at `<GCP_INVOICE_PREFIX>/standalone/<financial-year>/<sha256>.pdf`.
The usual prefix is `invoices/`. No bucket ACL changes are made: **authenticated
app downloads do not make an already-public bucket private**.

The invoice number is unique within its April-March financial year; PDF SHA-256
is globally unique in the register. Exact PDF/metadata replay is idempotent.
Different content or details under the same identity returns 409. Numbers and
matching original PDF checksums already in Transactions are rejected, including
soft-deleted transactions, to avoid unintentional duplicate accounting.

## Generate future final invoices

Run from `mystock` using its venv:

```bash
# Set KC_API_URL to the reviewed backend base ending in /api.
# Set KC_API_TOKEN securely from an ADMIN or STAFF login; never put it in files.
venv/bin/python -m scripts.pdf_invoice generate invoice.json /path/to/invoice.pdf
```

Example input (replace with confirmed customer, tax and product details):

```json
{
  "invoice_number": "39",
  "invoice_date": "2026-09-24",
  "customer_name": "Example Buyer",
  "customer_gstin": null,
  "customer_address": null,
  "customer_phone": null,
  "tax_type": "igst",
  "line_items": [
    {
      "name": "Example product",
      "quantity": 100,
      "unit_price": "10.00",
      "tax_rate": "18.00",
      "hsn_code": "39199010"
    }
  ],
  "total_amount": "1180.00",
  "notes": null
}
```

The CLI reads active seller settings from the backend's configured database
(read-only); they must match the selected API/company. It reuses the standard
invoice renderer, stores line-item snapshots, and uploads through the API.
It does not guess applicable GST/HSN or adjust quantities. `total_amount` may be
omitted to round up to the next rupee; a supplied amount permits only a small
round-off, not an undisclosed discount. Invoice numbers are explicit, not
automatically allocated; check the register and existing issued bills first.
Invoices show their invoice date only. The shared renderer does not calculate
or print a payment due date for either transaction or standalone bills.

The output PDF and `.metadata.json` sidecar are retained locally. Success is
reported only after registration and a checksum-matched cloud download; the
`.registered.json` receipt contains the saved record.

If the user explicitly requests no printed invoice number, the generation spec
may set `"show_invoice_number": false`. The register still requires an identifier:
obtain approval for an internal reference in `invoice_number` and explain it in
`notes`. That reference and the invoice-number label are omitted from the PDF;
normal invoices print their number by default. Do not silently treat an internal
archive reference as an issued invoice serial number.

For an unissued draft only, pass `--preview`. This is explicitly unregistered.
The older `scripts.preview_invoice` accepts earlier item specs but now also
archives by default; it requires `--preview` to opt out.

## Company bank details

Company Settings stores optional `bank_name`, `bank_account_number`, `bank_branch`
and `bank_ifsc` fields. Apply migration `0015_company_bank_details` before deploying
the updated backend. Back up the database and obtain approval before migrating.
Bank values belong in company settings, not source code or the migration.
On 06-Oct-2026, the live database was backed up, migration `0015` applied, and
confirmed bank values saved with approval. Backend/frontend deployment still
requires separate approval.

The authenticated settings API is `GET /api/settings/company`; administrators
update it with `PUT /api/settings/company`. Send all four bank fields together
when changing them. Bank name, account number (a string, preserving leading
zeros), and IFSC are required when any bank details are configured; branch is
optional. Send all four as `null` to remove the bank section. Requests that do not
include bank fields preserve existing values.

Both transaction invoices and the tracked standalone CLI print the bank section
on the final page, with measured space reserved before pagination. Empty bank
settings preserve the prior layout. The settings UI and transaction renderer
need deployment before this applies to bills generated by the live web app.
Historical PDFs remain unchanged; updating settings does not overwrite archived
invoice objects. Any explicitly approved correction must retain the original
PDF and metadata for recovery, verify the new cloud object, and preserve all
unrelated invoice/accounting data.
For an approved same-number file correction, retain the original register row
and bytes, upload a new checksum-addressed object without overwriting the old
one, and condition the file-reference update on the original checksum and
metadata hash. Preserve the invoice identity and financial metadata. Re-import
the exact revised PDF and unchanged metadata through the tracked CLI to verify
the existing register entry and authenticated cloud download before delivering it.
This is an administrative recovery procedure, not a public edit API.

## Interrupted uploads and historical imports

```bash
venv/bin/python -m scripts.pdf_invoice import invoice.metadata.json invoice.pdf
```

Import sends the original PDF unchanged. Metadata uses the API fields, including
`subtotal`, `cgst`, `sgst`, `igst`, `round_off`, `total_amount`; use
`source: "uploaded"` and `line_items: null` for manually entered historical bills.
Keep a generated bill's original sidecar unchanged.

An interrupted upload leaves a visible **Upload incomplete** row and reserves its
number. Retry with the same PDF and metadata using the CLI or the row's
**Retry upload** action. The GCS create-only precondition permits reuse only when
existing object bytes match. Do not re-render, edit details, or allocate another
number to recover. If a success response was lost, replaying the same request
returns the existing record.

Historical import is a separate approved step. Import verified final standalone
originals only, not drafts/revisions or ordinary transaction PDFs. Resolve aliases,
replacement bills and conflicting totals manually before importing. An empty
register does not mean old invoices did not exist, and this register alone is not
a complete GST return or reconciliation.

## Offline regression cases

`tests/test_pdf_invoices.py` uses standard-library unittest, in-memory SQLite,
mocked storage and a router-only FastAPI app with no startup database check.
`tests/test_invoice_bank_details.py` covers bank-field validation, CLI seller
loading, and shared-renderer bank text, wrapping and final-page placement.
Both are offline; run only with permission:

```bash
venv/bin/python -m unittest discover -s tests -p 'test_pdf_invoices.py'
venv/bin/python -m unittest discover -s tests -p 'test_invoice_bank_details.py'
```

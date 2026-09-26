# PDF Bills

The **PDF Bills** screen archives standalone issued invoices alongside (not inside)
the existing Transactions workflow. It does not change inventory, contacts,
customer balances or payments. Regular transaction PDFs remain in Transactions.

## Rollout gate

This feature's public backend/frontend are **not deployed**. On 25-Sep-2026,
the user approved applying migration `0014_pdf_invoice_register` and archiving
the existing original SALE-0046 before creating the normal SM57 sale SALE-0047.
Those database/archive steps are complete; no other historical PDFs were imported.
Do not perform additional imports, commits or deployment without approval.
Tests were explicitly declined for this implementation session.

For another environment, after approval, back up the database and apply migration
`0014_pdf_invoice_register` (parent: `0013_per_item_gst`), then deploy backend and
frontend. For the live environment, the migration is already applied; public
backend/frontend deployment remains pending. The new backend requires the table even for normal sales because sale
number generation skips numbers reserved by standalone invoices. Do not start
the new backend against a database without this migration.
Apply the reviewed Nginx `client_max_body_size 12m` setting as well (10 MiB PDF
plus multipart metadata); the deployment template includes it for HTTP and HTTPS.

The frontend's existing API base points to production. Do not use it for local
upload experimentation. Static checks do not issue HTTP requests.

## UI and API

All authenticated roles can search/filter the register and view/download PDFs.
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

The output PDF and `.metadata.json` sidecar are retained locally. Success is
reported only after registration and a checksum-matched cloud download; the
`.registered.json` receipt contains the saved record.

For an unissued draft only, pass `--preview`. This is explicitly unregistered.
The older `scripts.preview_invoice` accepts earlier item specs but now also
archives by default; it requires `--preview` to opt out.

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
Run only with permission:

```bash
venv/bin/python -m unittest discover -s tests -p 'test_pdf_invoices.py'
```

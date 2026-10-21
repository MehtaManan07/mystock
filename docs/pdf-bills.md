# PDF Bills

The **PDF Bills** screen archives standalone issued invoices alongside (not inside)
the existing Transactions workflow. It does not change inventory, contacts,
customer balances or payments. Regular transaction PDFs remain in Transactions.

## Rollout gate

The existing PDF Bills backend/frontend and migration
`0014_pdf_invoice_register` are live. Historical imports have been performed with
approval. Do not perform additional imports, commits or deployment without approval.
The customer-link changes below require migration `0018_pdf_invoice_customer`
before the revised backend, CLI and frontend are used. Deployment still requires
separate approval.
On 20-Oct-2026, that migration was applied with approval: all 29 existing PDF
records (25 active, 4 retired) were linked to the 9 saved customers. Invoice
snapshots, archive references and accounting data were unchanged. The revised
backend/frontend code remains local and undeployed.

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

The shared-numbering changes require migration `0019_pdf_invoice_numbering`.
It only adds a number-reservation table; it does not renumber or rewrite invoices.
This migration has **not been applied**. After review/approval, pause sales/PDF
writes, apply the migration, replace all old backend writers, then update the CLI
and frontend before resuming writes. Old writers do not participate in the shared
numbering lock. Do not deploy the new backend against an unmigrated database.

All authenticated roles can search/filter the register and view/download PDFs.
The list sorts by date added (`created_at`), newest first, with descending record
ID breaking timestamp ties across pages. Printed invoice dates do not affect
this order; the From/To date filters still apply to the printed invoice date.
ADMIN and STAFF can select a saved customer, upload an issued PDF (maximum 10 MiB)
and enter the printed invoice details. New registrations require `customer_id`;
create missing customers in Contacts first. Copy amounts exactly:
taxable + CGST + SGST + IGST + round-off
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
| `POST /pdf-invoices/reserve-number` | ADMIN/STAFF: reserve a new sales number with `request_id` (UUID), `customer_id`, and `spec_sha256` |

Metadata is stored in Postgres `pdf_invoices`. Objects are stored in the existing
bucket at `<GCP_INVOICE_PREFIX>/standalone/<financial-year>/<sha256>.pdf`.
The usual prefix is `invoices/`. No bucket ACL changes are made: **authenticated
app downloads do not make an already-public bucket private**.

The invoice number is unique within its April-March financial year; PDF SHA-256
is globally unique in the register. Exact PDF/metadata replay is idempotent.
Different content or details under the same identity returns 409. Numbers and
matching original PDF checksums already in Transactions are rejected, including
soft-deleted transactions, to avoid unintentional duplicate accounting.

## Invoice numbering and download names

New sales transactions and CLI-generated standalone bills use **one shared
`SALE-####` series**. The allocator considers the highest numeric SALE suffix in
both registers and all PDF number reservations, including pending, retired and
unused entries. Plain historical numbers such as `46` are not SALE suffixes:
`46` and `SALE-0046` remain different, unchanged invoice identities. Purchase
numbering stays in its existing `PUR-####` series. There is no annual reset.

Sales creation, PDF number reservation and PDF registration/import hold the same
PostgreSQL transaction-scoped advisory lock until commit/rollback. The reservation
endpoint persists a number before local rendering. Repeating its request UUID
with the same customer, user and specification hash returns the same number;
changing those details returns a conflict. A reservation creates no PDF invoice,
GST snapshot, stock movement, balance or payment entry. Unused reserved numbers
are retained, not recycled; keep the request receipt when a bill is abandoned.

Upload/import is **only for PDFs already issued** and must copy their original
number, even if it belongs to an older numbering scheme. It never assigns a new
number to existing bytes. An import cannot take a number reserved for a different
bill. The existing immutable-PDF/metadata replay rules continue to apply.

All download paths and new CLI output use
`<invoice-number>_<CUSTOMER-NAME>_<YYYY-MM-DD>.pdf`, for example:

```text
46_AZAD-IMITATION_2026-10-20.pdf
SALE-0063_DABSTER-INTERNATIONAL-PRIVATE-LIMITED_2026-10-21.pdf
```

Customer names are normalized to uppercase ASCII with hyphen separators, capped
at 80 characters. Invoice-number slashes are percent-encoded (`29/26-27` becomes
`29%2F26-27`) rather than collapsed into hyphens. PDF register/contact responses
include `download_filename`; transaction signed URLs set the same filename via
Content-Disposition. Historical PDF bytes, GCS keys, invoice numbers, and files
already in Downloads are not renamed or regenerated.

## Contact bill history

The contact detail page's **Bills** list combines sales, purchases and standalone
PDF invoices through authenticated `GET /contacts/{contact_id}/bills` (`page`,
`page_size`, maximum 100). Pagination applies to the combined history, newest
invoice date first, then creation time, source and ID for stable ties.

PDFs are retrieved by the indexed `pdf_invoices.customer_id` foreign key to
`contacts.id`, not by names or GSTINs at read time. Renaming a customer or changing
their GSTIN does not move or hide historical bills. The invoice's printed customer
name, GSTIN, address and phone remain immutable snapshots, separate from this link.

Migration `0018_pdf_invoice_customer` adds the link and backfills existing records,
including retired PDFs. It uses a unique active contact with the same normalized
GSTIN, or a unique exact normalized name only when both sides lack GSTINs.
Ambiguous or unmatched records remain null for explicit administrative resolution;
inspect every unresolved row before considering a backfill complete. Never use
fuzzy matching or create contacts as a migration side effect.

The column remains nullable for historical exceptions and compatibility with the
old deployed writer during rollout. The revised API requires an explicit, active
customer (or both-type contact) for every new registration. It rejects conflicting
GSTINs when both the invoice and contact have one. Old sidecars without
`customer_id` can still retry an existing invoice without changing its link.
An explicit different ID on a replay is rejected. The link is excluded from the
printed-metadata checksum, preserving historical hashes and exact-byte retries.

Deleted records are excluded. Pending PDF uploads remain visible as incomplete
and link to the PDF register; ready PDFs use the existing authenticated preview
and download. PDF bills never acquire a paid/unpaid status or contribute to the
contact balance. This is a combined view, not a merge of accounting records.
After approval, back up the affected data, apply `0018_pdf_invoice_customer` and
verify the links and unchanged financial/archive fields. Deploy the backend before
the updated frontend. Avoid new PDF registrations through the old writer between
the backfill and deployment: it can still create null links. Reconcile any such
rows explicitly before rollout is complete. Deployment and tests still require
explicit approval.

## Generate future final invoices

Run from `mystock` using its venv:

```bash
# Set KC_API_URL to the reviewed backend base ending in /api.
# Set KC_API_TOKEN securely from an ADMIN or STAFF login; never put it in files.
venv/bin/python -m scripts.pdf_invoice generate invoice.json /path/to/private-bill-directory
```

Example input (replace with confirmed customer, tax and product details):

```json
{
  "invoice_date": "2026-09-24",
  "customer_id": 123,
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

Replace `customer_id` with the actual saved customer's ID; it is not printed.
Final generation requires it before rendering, while an unissued `--preview`
may omit it. The CLI reads active seller settings from the backend's configured database
(read-only); they must match the selected API/company. It reuses the standard
invoice renderer, stores line-item snapshots, and uploads through the API.
It does not guess applicable GST/HSN or adjust quantities. `total_amount` may be
omitted to round up to the next rupee; a supplied amount permits only a small
round-off, not an undisclosed discount. Invoice numbers are
automatically allocated by the shared reservation endpoint. Omit `invoice_number`
for new final bills; specifying one is rejected. Check for duplicate orders before
starting a new run, and use a separate existing private output directory per bill.
For an unregistered buyer, leave `customer_gstin` null and include the confirmed
state name and state code in `customer_address`. Do not substitute a PAN for a
GSTIN. The renderer omits the GSTIN-derived buyer-state line when no GSTIN is
provided, rather than printing "Not Specified, Code: 00". This rendering correction
is local and requires deployment before it affects PDFs generated by the web app.
Invoices show their invoice date only. The shared renderer does not calculate
or print a payment due date for either transaction or standalone bills.

The CLI writes `generation-request.json` before requesting a number, then saves
`number-reservation.json`. A timeout during reservation is recovered by repeating
`generate` with the **same spec and directory**, retaining the same request UUID.
Do not delete these receipts or use a fresh directory to retry a timed-out issue.
Once a PDF or metadata sidecar exists, `generate` refuses to overwrite it; recover
with exact-byte `import`, not another render. A reservation is not proof of issue.

The descriptively named output PDF and `.metadata.json` sidecar are retained locally. Success is
reported only after registration and a checksum-matched cloud download; the
`.registered.json` receipt contains the saved record.

If the user explicitly requests no printed invoice number, the generation spec
may set `"show_invoice_number": false`. The register still requires an identifier:
explain the automatically reserved SALE reference in `notes` and obtain approval
to omit it from the printed document. That reference and the invoice-number label are omitted from the PDF;
normal invoices print their number by default. Do not silently treat an internal
archive reference as an issued invoice serial number.

For an unissued draft only, pass `--preview`. This is explicitly unregistered,
does not reserve a number, and defaults to `DRAFT` if no preview number is supplied.
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

`tests/test_invoice_numbering.py` covers shared allocation, durable reservation
retries, historical identities, CLI recovery and descriptive download names.
`tests/test_contact_bills.py` also checks filenames use the PDF's original buyer
snapshot after contact edits. These tests use SQLite/mocks; they do not exercise
PostgreSQL lock contention or make production/cloud requests.

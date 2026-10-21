"""Generate and archive standalone invoices, or import an existing issued PDF.

Run from the backend root with `python -m scripts.pdf_invoice --help`.
KC_API_URL and KC_API_TOKEN select an authenticated running API. No stock,
balance, contact or payment records are created.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

import requests
from fastapi import HTTPException
from sqlalchemy import select

from app.core.db.engine import SessionLocal
from app.core.invoice_filenames import invoice_filename
from app.modules.pdf_invoices.render import GeneratePdfInvoice, render_invoice
from app.modules.pdf_invoices.schemas import PdfInvoiceMetadata, PdfInvoiceNumberResponse, PdfInvoiceResponse
from app.modules.pdf_invoices.service import validate_pdf
from app.modules.settings.models import CompanySettings


def api_config() -> tuple[str, str]:
    url = os.environ.get("KC_API_URL", "").rstrip("/")
    token = os.environ.get("KC_API_TOKEN", "")
    parsed = urlparse(url)
    if not token or not url:
        raise ValueError("Set KC_API_URL (ending in /api) and KC_API_TOKEN from an ADMIN/STAFF login")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("KC_API_URL must not contain credentials, a query or a fragment")
    if not parsed.hostname or not parsed.path.endswith("/api"):
        raise ValueError("KC_API_URL must include a hostname and end in /api")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("Use HTTPS for the API, or HTTP only for localhost")
    return url, token


def load_seller() -> SimpleNamespace:
    with SessionLocal() as db:
        settings = db.execute(select(CompanySettings).where(
            CompanySettings.is_active.is_(True), CompanySettings.deleted_at.is_(None)
        ).limit(1)).scalar_one()
        fields = (
            "company_name", "company_address_line1", "company_address_line2",
            "company_address_line3", "seller_gstin", "seller_phone", "seller_email",
            "terms_and_conditions", "bank_name", "bank_account_number", "bank_branch", "bank_ifsc",
        )
        seller = SimpleNamespace(**{key: getattr(settings, key) for key in fields}, hsn_code="-")
        db.rollback()
    return seller


def register_pdf(metadata: PdfInvoiceMetadata, path: Path) -> dict:
    url, token = api_config()
    content = path.read_bytes()
    validate_pdf(content)
    response = requests.post(
        f"{url}/pdf-invoices",
        headers={"Authorization": f"Bearer {token}"},
        data={"metadata": metadata.model_dump_json()},
        files={"file": (path.name, content, "application/pdf")},
        timeout=(15, 180),
        allow_redirects=False,
    )
    if not 200 <= response.status_code < 300:
        try:
            error = response.json()
            detail = response.reason
            if isinstance(error, dict):
                detail = error.get("detail") or detail
                if isinstance(error.get("error"), dict):
                    detail = error["error"].get("message") or detail
        except ValueError:
            detail = response.reason
        raise RuntimeError(
            f"Registration failed (HTTP {response.status_code}): {detail}. Local PDF retained. "
            "Correct the error and retry import with the SAME PDF and metadata; "
            "do not regenerate it or issue a new number."
        )
    payload = response.json()
    record = PdfInvoiceResponse.model_validate(payload.get("data", payload)).model_dump(mode="json")
    if record.get("upload_status") != "ready" or record.get("pdf_sha256") != hashlib.sha256(content).hexdigest():
        raise RuntimeError("Server did not confirm a matching archived PDF; check the register before retrying")
    expected = metadata.model_dump(
        mode="json", exclude={"customer_id"} if metadata.customer_id is None else set()
    )
    actual = PdfInvoiceMetadata.model_validate({key: record[key] for key in expected}).model_dump(mode="json")
    if metadata.customer_id is None:
        actual.pop("customer_id")
    if actual != expected:
        raise RuntimeError("Server returned different invoice details; registration was not confirmed")
    stored = requests.get(
        f"{url}/pdf-invoices/{record['id']}/file",
        headers={"Authorization": f"Bearer {token}"},
        timeout=(15, 180), allow_redirects=False,
    )
    if stored.status_code != 200 or hashlib.sha256(stored.content).hexdigest() != record["pdf_sha256"]:
        raise RuntimeError("Invoice was registered, but cloud read-back was not confirmed. Retry import to verify")
    receipt = path.with_suffix(".registered.json")
    receipt.write_text(json.dumps(record, indent=2))
    print(f"Archived invoice {metadata.invoice_number}, register id {record['id']}: {path}")
    return record


def reserve_number(spec: GeneratePdfInvoice, directory: Path) -> str:
    url, token = api_config()
    canonical = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    request_path = directory / "generation-request.json"
    if request_path.exists():
        request = json.loads(request_path.read_text())
        if (request["spec_sha256"] != fingerprint or request["customer_id"] != spec.customer_id
                or request["api_url"] != url):
            raise ValueError("This output directory belongs to a different bill or API; use its original spec to recover")
    else:
        request = {
            "request_id": str(uuid4()), "customer_id": spec.customer_id,
            "spec_sha256": fingerprint, "api_url": url,
        }
        # Retain the idempotency key before making a request that may time out after committing.
        with request_path.open("x") as handle:
            json.dump(request, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
    response = requests.post(
        f"{url}/pdf-invoices/reserve-number",
        headers={"Authorization": f"Bearer {token}"},
        json={key: value for key, value in request.items() if key != "api_url"},
        timeout=(15, 60), allow_redirects=False,
    )
    if response.status_code != 201:
        raise RuntimeError(
            f"Number reservation failed (HTTP {response.status_code}): {response.text}. "
            "Retry generate with the same spec and directory; do not choose a number manually."
        )
    payload = response.json()
    reserved = PdfInvoiceNumberResponse.model_validate(payload.get("data", payload))
    if (str(reserved.request_id) != request["request_id"] or reserved.customer_id != spec.customer_id
            or reserved.spec_sha256 != fingerprint):
        raise RuntimeError("API returned a different numbering reservation; stop and inspect before issuing")
    receipt_path = directory / "number-reservation.json"
    if receipt_path.exists():
        if PdfInvoiceNumberResponse.model_validate_json(receipt_path.read_text()) != reserved:
            raise RuntimeError("The saved invoice number changed; stop and inspect before issuing")
    else:
        with receipt_path.open("x") as handle:
            handle.write(reserved.model_dump_json(indent=2))
    return reserved.invoice_number


def generate(spec: GeneratePdfInvoice, output: Path, preview: bool = False) -> Path:
    if not output.is_dir():
        raise ValueError("Output must be an existing per-bill directory; filenames are generated automatically")
    if not preview and spec.invoice_number is not None:
        raise ValueError("Omit invoice_number for new bills; use import to archive an already-issued invoice")
    if not preview and spec.customer_id is None:
        raise ValueError("Supply the existing customer's customer_id before generating a final invoice")
    number = (spec.invoice_number or "DRAFT") if preview else reserve_number(spec, output)
    spec = spec.model_copy(update={"invoice_number": number})
    output = output / invoice_filename(number, spec.customer_name, spec.invoice_date)
    metadata_path = output.with_suffix(".metadata.json")
    if output.exists() or metadata_path.exists():
        raise FileExistsError("Output or metadata already exists. Retry import rather than overwriting an invoice")
    metadata, content = render_invoice(spec, load_seller())
    # Keep a durable sidecar and the exact bytes even if the upload fails.
    with metadata_path.open("x") as f:
        f.write(metadata.model_dump_json(indent=2))
    with output.open("xb") as f:
        f.write(content)
    if preview:
        print(f"UNREGISTERED PREVIEW: {output}. Do not issue until imported into PDF Bills.")
    else:
        register_pdf(metadata, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("generate", help="Render the standard PDF and archive it before reporting success")
    create.add_argument("spec", type=Path)
    create.add_argument("output", type=Path, help="Existing private per-bill directory; number and filename are automatic")
    create.add_argument("--preview", action="store_true", help="Explicitly opt out of archiving for a draft only")
    upload = commands.add_parser("import", help="Archive an existing PDF unchanged (safe to retry identical input)")
    upload.add_argument("metadata", type=Path)
    upload.add_argument("pdf", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        generate(GeneratePdfInvoice.model_validate_json(args.spec.read_text()), args.output, args.preview)
    else:
        register_pdf(PdfInvoiceMetadata.model_validate_json(args.metadata.read_text()), args.pdf)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, requests.RequestException, HTTPException) as exc:
        raise SystemExit(f"Invoice NOT confirmed archived: {exc}") from None

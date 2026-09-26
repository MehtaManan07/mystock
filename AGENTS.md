# Invoice workflow

- Before generating or importing standalone customer bills, read
  `docs/pdf-bills.md`.
- Final standalone invoices must use `python -m scripts.pdf_invoice generate`
  or `import`. Do not use ad hoc PDF scripts that bypass the register.
- A bill is not confirmed archived until API registration and checksum-verified
  cloud read-back succeed. Retain the PDF, metadata sidecar and registration
  receipt. On failure, report it explicitly and retry the original bytes.
- Use `--preview` only when the user explicitly wants an unissued draft.
- Preserve the user's confirmed date, number, buyer, HSN/GST, product rates and
  inclusive total. Never invent missing tax details or duplicate a known invoice.
- Standalone bills do not create transactions, change stock or affect balances.
- Never run tests, apply live migrations, import historical bills, commit or deploy
  without the user's approval. Leave implementation changes for local review.

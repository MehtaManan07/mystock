from datetime import date
import re
import unicodedata
from urllib.parse import quote


def invoice_filename(number: str, customer_name: str, invoice_date: date) -> str:
    name = unicodedata.normalize("NFKD", customer_name).encode("ascii", "ignore").decode()
    customer = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:80].rstrip("-") or "CUSTOMER"
    # Encode separators instead of collapsing distinct invoice numbers such as 29/26 and 29-26.
    return f"{quote(number, safe='-')}_{customer}_{invoice_date.isoformat()}.pdf"

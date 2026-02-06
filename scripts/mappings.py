import csv
import json
from typing import Dict, List

# File paths
SHOPIFY_CSV = "products.csv"
INTERNAL_CSV = "shopify.csv"
OUTPUT_JSON = "vendor_sku_mappings.json"


def build_sku_mapping() -> Dict[str, str]:
    """
    Build mapping from company_sku (your internal SKU) to vendor_sku (Shopify SKU).
    Returns dict: {company_sku: vendor_sku}
    """
    sku_mapping = {}
    
    # Read internal pricing data to get company_sku
    internal_data = {}
    with open(INTERNAL_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            full_sku = row['Sku'].strip()
            company_sku = row['Sku description (space not use )'].strip()
            if full_sku and company_sku:
                internal_data[full_sku] = company_sku
    
    # Read Shopify data to get vendor_sku (Shopify SKU)
    with open(SHOPIFY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor_sku = row['Variant SKU'].strip()  # This is the Shopify SKU
            
            if vendor_sku and vendor_sku in internal_data:
                company_sku = internal_data[vendor_sku]
                sku_mapping[company_sku] = vendor_sku
    
    return sku_mapping


def generate_vendor_sku_payload(sku_mapping: Dict[str, str], vendor_id: int = 1) -> List[Dict]:
    """
    Generate API payload structure for vendor SKU mappings.
    Note: product_id needs to be filled after products are created.
    """
    payloads = []
    
    for company_sku, vendor_sku in sku_mapping.items():
        payload = {
            "company_sku": company_sku,  # For reference only
            "product_id": "REPLACE_WITH_ACTUAL_PRODUCT_ID",  # To be filled
            "vendor_id": vendor_id,
            "vendor_sku": vendor_sku
        }
        payloads.append(payload)
    
    return payloads


def main():
    """
    Generate vendor SKU mapping JSON file.
    """
    print("🚀 Generating vendor SKU mappings...\n")
    
    # Build mappings
    sku_mapping = build_sku_mapping()
    
    print(f"✅ Found {len(sku_mapping)} SKU mappings\n")
    
    # Generate payloads
    payloads = generate_vendor_sku_payload(sku_mapping)
    
    # Write to JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(payloads, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Saved to: {OUTPUT_JSON}\n")
    
    # Print sample
    if payloads:
        print("📦 Sample mapping:")
        print(json.dumps(payloads[0], indent=2))
        print("\n⚠️  Note: Replace 'REPLACE_WITH_ACTUAL_PRODUCT_ID' with actual product IDs after creating products")


if __name__ == "__main__":
    main()
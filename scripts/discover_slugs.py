#!/usr/bin/env python3
"""One-time script to discover endoflife.date API slugs for hardware vendors.

Fetches the full product list from endoflife.date and prints every product
whose name contains any of the target vendor keywords.
"""

import json
import urllib.request

KEYWORDS = [
    "dell", "cisco", "supermicro", "intel", "amd", "nvidia",
    "juniper", "arista", "broadcom", "mellanox",
]

API_URL = "https://endoflife.date/api/all.json"


def main():
    print(f"Fetching {API_URL} ...")
    with urllib.request.urlopen(API_URL, timeout=15) as resp:
        products = json.loads(resp.read().decode())

    print(f"Total products on endoflife.date: {len(products)}\n")

    matches = []
    for product in products:
        product_lower = product.lower()
        for kw in KEYWORDS:
            if kw in product_lower:
                matches.append((kw, product))
                break

    if not matches:
        print("No matches found for any keyword.")
        return

    print(f"Found {len(matches)} matching product(s):\n")
    print(f"{'Keyword':<12} {'Slug (product name)':<30} {'Sample URL'}")
    print("-" * 80)
    for kw, slug in sorted(matches):
        url = f"https://endoflife.date/api/{slug}.json"
        print(f"{kw:<12} {slug:<30} {url}")

    # Also verify each slug returns 200
    print("\n--- Verification (HTTP status for each slug) ---")
    for kw, slug in sorted(matches):
        url = f"https://endoflife.date/api/{slug}.json"
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"  {slug}: {resp.status}")
        except Exception as e:
            print(f"  {slug}: FAILED ({e})")


if __name__ == "__main__":
    main()

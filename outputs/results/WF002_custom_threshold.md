# WF002_custom_threshold

_What this checks: User-supplied threshold overrides the 10% default_

**Request:** Validate our product prices against the vendor list and flag anything more than 20% off.

**Selected Workflow:** WF002 - Product Price Validation
**Routing:** Claude tool calling (confidence: high) - User wants product prices validated against the vendor price list with a custom threshold.
**Status:** ⚠️ Completed with flags

### Steps Executed
1. ✅ **Load product prices** [`read_table`, `read_table`] - Loaded 22 rows x 11 columns from products.csv → Loaded 22 rows x 3 columns from vendor_prices.csv
2. ✅ **Match products by SKU** [`join_tables`, `filter_rows`, `filter_rows`, `select_columns`] - Joined 22 + 22 rows on 'sku' (outer): 21 matched, 1 missing_from_vendor_list, 1 missing_from_internal_catalog → 21 of 23 rows match → 2 of 23 rows match
3. ✅ **Compare internal and vendor prices** [`compute_column`] - Calculated 'price_difference' = vendor_price - price
4. ✅ **Calculate percentage difference** [`compute_column`] - Calculated 'difference_pct' = (vendor_price - price) / price * 100
5. ⚠️ **Flag exceptions** [`compute_column`, `compare_to_threshold`, `select_columns`, `filter_rows`] - Calculated 'abs_difference_pct' = abs(difference_pct) → 1 product(s) differ from the vendor price by more than 20% → 1 of 21 rows match

### Result
Validation matched **21 products** against the vendor list, and **1** is more than 20% off: **SKU-1010 Waterproof Rain Jacket**, priced at $110.00 internally vs. $137.50 from the vendor (a **$27.50 / 25.0%** difference). The other 20 matched products are within the threshold; the next largest gaps are SKU-1003 Slim Fit Denim Jeans (15.0%) and SKU-1007 Running Sneakers (-12.49%). Two SKUs could not be matched: SKU-1016 Sports Bra is missing from the vendor list, and SKU-3001 (vendor price $29.00) is missing from the internal catalog.

#### Price exceptions

| sku | product_name | internal_price | vendor_price | price_difference | difference_pct | is_exception |
|---|---|---|---|---|---|---|
| SKU-1010 | Waterproof Rain Jacket | 110 | 137.5 | 27.5 | 25 | True |

#### Validation report (all matched products)

| sku | product_name | internal_price | vendor_price | price_difference | difference_pct | is_exception |
|---|---|---|---|---|---|---|
| SKU-1010 | Waterproof Rain Jacket | 110 | 137.5 | 27.5 | 25 | True |
| SKU-1003 | Slim Fit Denim Jeans | 59 | 67.85 | 8.85 | 15 | False |
| SKU-1007 | Running Sneakers | 89 | 77.88 | -11.12 | -12.49 | False |
| SKU-2003 | Quilted Shacket | 120 | 133.2 | 13.2 | 11 | False |
| SKU-1013 | Baseball Cap | 22 | 19.69 | -2.31 | -10.5 | False |
| SKU-1005 | Leather Belt | 35 | 38.5 | 3.5 | 10 | False |
| SKU-1015 | Yoga Leggings | 55 | 60.45 | 5.45 | 9.91 | False |
| SKU-1011 | Puffer Vest | 85 | 78.2 | -6.8 | -8 | False |
| SKU-2006 | Plaid Wool Scarf | 59 | 63.13 | 4.13 | 7 | False |
| SKU-1008 | Hiking Boots | 129 | 136.74 | 7.74 | 6 | False |
| SKU-2001 | Merino Wool Turtleneck | 95 | 99.75 | 4.75 | 5 | False |
| SKU-1004 | Wool Blend Sweater | 79 | 82.55 | 3.55 | 4.49 | False |
| SKU-2005 | Cashmere Beanie | 49 | 47.04 | -1.96 | -4 | False |
| SKU-1002 | Classic Cotton T-Shirt | 19.99 | 19.39 | -0.6 | -3 | False |
| SKU-1012 | Linen Shirt | 49 | 50.47 | 1.47 | 3 | False |
| SKU-1001 | Classic Cotton T-Shirt | 19.99 | 20.39 | 0.4 | 2 | False |
| SKU-2002 | Corduroy Overshirt | 75 | 73.5 | -1.5 | -2 | False |
| SKU-1006 | Canvas Tote Bag | 24 | 23.64 | -0.36 | -1.5 | False |
| SKU-1014 | Ankle Socks (3-Pack) | 12 | 12.12 | 0.12 | 1 | False |
| SKU-2004 | Chelsea Boots | 140 | 140.7 | 0.7 | 0.5 | False |
| SKU-1009 | Silk Scarf | 45 | 45 | 0 | 0 | False |

#### SKUs that could not be matched

| sku | product_name | price | vendor_price | match_status |
|---|---|---|---|---|
| SKU-1016 | Sports Bra | 39 |  | missing_from_vendor_list |
| SKU-3001 |  |  | 29 | missing_from_internal_catalog |

**Flags:**
- 1 product(s) differ from the vendor price by more than 20%

_Run run-20261014-185059-e2014a - 4.4s, LLM calls: 2, tokens: 7993 in / 361 out_

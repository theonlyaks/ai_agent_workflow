# WF001_global_threshold

_What this checks: Global threshold extracted from the request overrides per-product minimums_

**Request:** Which products have fewer than 10 units in stock and need reordering?

**Selected Workflow:** WF001 - Inventory Restock Check
**Routing:** Claude tool calling (confidence: high) - User asks which products are low on stock and need reordering, matching the inventory restock check.
**Status:** ✅ Completed

### Steps Executed
1. ✅ **Load inventory** [`read_table`] - Loaded 16 rows x 8 columns from inventory.csv
2. ✅ **Compare current stock with minimum threshold** [`compare_to_threshold`] - 4 product(s) have current_stock below the minimum threshold
3. ✅ **Identify low-stock products** [`filter_rows`] - 4 of 16 rows match
4. ✅ **Calculate reorder quantity** [`compute_column`] - Calculated 'suggested_reorder_qty' = effective_threshold * @multiplier - current_stock
5. ✅ **Generate restock list** [`select_columns`]

### Result
**4 products** are below the 10-unit threshold and need reordering. The most urgent is **Running Sneakers (SKU-1007)**, which is out of stock (0 units), followed by Waterproof Rain Jacket (5 units), Wool Blend Sweater (8 units) and Yoga Leggings (9 units). Suggested reorder quantities are 20, 15, 12 and 11 respectively. Note that the Wool Blend Sweater has the longest supplier lead time at 21 days. One row (SKU-1016) was skipped because its current stock or threshold was missing or not a number, so its status is unknown and should be checked manually.

#### Products requiring restock

| sku | product_name | category | current_stock | minimum_threshold | suggested_reorder_qty | supplier | lead_time_days |
|---|---|---|---|---|---|---|---|
| SKU-1007 | Running Sneakers | Footwear | 0 | 10 | 20 | Stride Supply | 14 |
| SKU-1010 | Waterproof Rain Jacket | Outerwear | 5 | 10 | 15 | RainGear | 12 |
| SKU-1004 | Wool Blend Sweater | Apparel | 8 | 10 | 12 | KnitHouse | 21 |
| SKU-1015 | Yoga Leggings | Activewear | 9 | 10 | 11 | Flexa Mfg | 9 |

**Warnings:**
- 1 row(s) skipped - 'current_stock' or its threshold is missing / not a number: SKU-1016

_Run run-20261014-185104-9c0b6c - 6.3s, LLM calls: 2, tokens: 5895 in / 348 out_

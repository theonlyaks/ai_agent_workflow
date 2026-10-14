# WF001_excel_test

_What this checks: Tests workflow selection and threshold logic_

**Request:** Which products need restocking?

**Selected Workflow:** WF001 - Inventory Restock Check
**Routing:** Claude tool calling (confidence: high) - User asks which products need restocking, matching the Inventory Restock Check workflow.
**Status:** ✅ Completed

### Steps Executed
1. ✅ **Load inventory** [`read_table`] - Loaded 16 rows x 8 columns from inventory.csv
2. ✅ **Compare current stock with minimum threshold** [`compare_to_threshold`] - 7 product(s) have current_stock below the minimum threshold
3. ✅ **Identify low-stock products** [`filter_rows`] - 7 of 16 rows match
4. ✅ **Calculate reorder quantity** [`compute_column`] - Calculated 'suggested_reorder_qty' = effective_threshold * @multiplier - current_stock
5. ✅ **Generate restock list** [`select_columns`]

### Result
**7 products** need restocking. The most urgent is **Running Sneakers (SKU-1007)**, which is out of stock (0 vs. a threshold of 20; suggested reorder 40, 14-day lead time from Stride Supply). Next are the **Waterproof Rain Jacket** (5 in stock vs. 15) and the **Wool Blend Sweater** (8 vs. 25, with the longest lead time at 21 days). Note that **SKU-1016** was skipped because its current stock or threshold is missing or not a number, so its status is unknown and needs checking.

#### Products requiring restock

| sku | product_name | category | current_stock | minimum_threshold | suggested_reorder_qty | supplier | lead_time_days |
|---|---|---|---|---|---|---|---|
| SKU-1007 | Running Sneakers | Footwear | 0 | 20 | 40 | Stride Supply | 14 |
| SKU-1010 | Waterproof Rain Jacket | Outerwear | 5 | 15 | 25 | RainGear | 12 |
| SKU-1004 | Wool Blend Sweater | Apparel | 8 | 25 | 42 | KnitHouse | 21 |
| SKU-1015 | Yoga Leggings | Activewear | 9 | 30 | 51 | Flexa Mfg | 9 |
| SKU-1006 | Canvas Tote Bag | Accessories | 12 | 15 | 18 | BagMakers | 7 |
| SKU-1012 | Linen Shirt | Apparel | 14 | 20 | 26 | LinenLab | 10 |
| SKU-1002 | Classic Cotton T-Shirt | Apparel | 18 | 40 | 62 | CottonCo | 7 |

**Warnings:**
- 1 row(s) skipped - 'current_stock' or its threshold is missing / not a number: SKU-1016

_Run run-20261014-184845-9d5398 - 4.6s, LLM calls: 2, tokens: 6221 in / 299 out_

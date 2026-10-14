# router_ambiguous_request

_What this checks: Router asks a clarifying question, then routes the answer_

**Request:** Can you help me with something?

**Selected Workflow:** WF001 - Inventory Restock Check
**Routing:** Claude tool calling (confidence: high) - User asks which products need restocking, matching the Inventory Restock Check workflow.
**Status:** ✅ Completed

**Conversation:**
> **User:** Can you help me with something?
> **Assistant:** Happy to help! What do you need? I can check inventory restocking, validate product prices, process vendor files, generate product descriptions, look up order status, find duplicate products, create campaign briefs, classify SEO keywords, assign tasks to employees, or report on workflow performance.
> **User:** I need to know which products need restocking

### Steps Executed
1. ✅ **Load inventory** [`read_table`] - Loaded 16 rows x 8 columns from inventory.csv
2. ✅ **Compare current stock with minimum threshold** [`compare_to_threshold`] - 7 product(s) have current_stock below the minimum threshold
3. ✅ **Identify low-stock products** [`filter_rows`] - 7 of 16 rows match
4. ✅ **Calculate reorder quantity** [`compute_column`] - Calculated 'suggested_reorder_qty' = effective_threshold * @multiplier - current_stock
5. ✅ **Generate restock list** [`select_columns`]

### Result
**7 products** need restocking. The most urgent is **Running Sneakers (SKU-1007)**, which is out of stock (0 vs. a threshold of 20; suggested reorder 40, supplier Stride Supply, 14-day lead time). Next are **Waterproof Rain Jacket** (5 in stock vs. 15 minimum, reorder 25), **Wool Blend Sweater** (8 vs. 25, reorder 42, 21-day lead time, the longest), and **Yoga Leggings** (9 vs. 30, reorder 51). Canvas Tote Bag, Linen Shirt and Classic Cotton T-Shirt are also below threshold. Warning: **SKU-1016** was skipped because its current stock or threshold is missing or not a number, so its restock status is unknown.

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

_Run run-20261014-185131-2b181d - 6.4s, LLM calls: 3, tokens: 10961 in / 559 out_

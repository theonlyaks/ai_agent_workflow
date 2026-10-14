# WF006_excel_test

_What this checks: Tests similarity and confidence_

**Request:** Find likely duplicate products in the catalog.

**Selected Workflow:** WF006 - Duplicate Product Detection
**Routing:** Claude tool calling (confidence: high) - User asks to find duplicate products in the catalog.
**Status:** ✅ Completed

### Steps Executed
1. ✅ **Load products** [`read_table`] - Loaded 18 rows x 8 columns from product_catalog.csv
2. ✅ **Normalize names/SKUs** [`normalize_text_columns`] - Normalised product_name, sku
3. ✅ **Compare identifiers** [`find_exact_matches`] - 1 pair(s) share the same sku_norm
4. ✅ **Compare product attributes** [`find_similar_pairs`] - 4 similar pair(s) out of 32 comparisons
5. ✅ **Group likely duplicates** [`group_pairs`] - 5 duplicate group(s) found
6. ✅ **Assign confidence** [`assign_label`] - 4 row(s) matched a rule for 'confidence'

### Result
The check found **5 likely duplicate groups**, each with 2 products. **G1** is a definite duplicate: SKU-1001 and sku-1001 (Classic Cotton T-Shirt / Classic Cotton Tee) match on SKU and on brand, color, material and size. **G2** (SKU-1003 / SKU-1203, Slim Fit Denim Jeans), **G4** (SKU-1010 / SKU-1910, Waterproof Rain Jacket) and **G5** (SKU-2004 / SKU-2104, Chelsea Boots) are possible duplicates with high confidence, with all attributes matching. **G3** (SKU-1007 / SKU-1077, Running Sneakers) is a possible duplicate with medium confidence because the material differs. No flags or warnings were raised.

#### Duplicate groups

| group_id | size | sku | product_name | has_exact_id_match | name_similarity | attribute_match | matching_fields | differing_fields | confidence |
|---|---|---|---|---|---|---|---|---|---|
| G1 | 2 | SKU-1001, sku-1001 | Classic Cotton T-Shirt \| Classic Cotton Tee | True | 87.5 | 1 | brand, color, material, size, sku_norm | - | Definite duplicate (exact SKU match) |
| G2 | 2 | SKU-1003, SKU-1203 | Slim Fit Denim Jeans \| Slim-Fit Denim Jeans | False | 100 | 1 | brand, color, material, name, size | - | Possible duplicate - high confidence |
| G3 | 2 | SKU-1007, SKU-1077 | Running Sneakers \| Running Sneaker | False | 96.8 | 0.75 | brand, color, name, size | material | Possible duplicate - medium confidence |
| G4 | 2 | SKU-1010, SKU-1910 | Waterproof Rain Jacket \| Rain Jacket - Waterproof | False | 100 | 1 | brand, color, material, name, size | - | Possible duplicate - high confidence |
| G5 | 2 | SKU-2004, SKU-2104 | Chelsea Boots \| Chelsea Boot | False | 96 | 1 | brand, color, material, name, size | - | Possible duplicate - high confidence |

_Run run-20261014-184931-729aff - 4.3s, LLM calls: 2, tokens: 6224 in / 369 out_

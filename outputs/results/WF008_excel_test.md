# WF008_excel_test

_What this checks: Tests classification and mapping_

**Request:** Classify these keywords and map them to pages.

**Selected Workflow:** WF008 - SEO Keyword Classification
**Routing:** Claude tool calling (confidence: high) - User wants keywords classified by intent and mapped to target pages, which matches SEO Keyword Classification.
**Status:** ✅ Completed

### Steps Executed
1. ✅ **Read keywords** [`read_table`, `read_table`] - Loaded 24 rows x 2 columns from keywords.csv → Loaded 7 rows x 3 columns from categories.csv
2. ✅ **Remove duplicates** [`drop_duplicate_rows`] - 2 duplicate row(s) removed, 22 unique
3. ✅ **Classify search intent** [`llm_classify`] - Classified 22 of 22 rows into 4 labels
4. ✅ **Map keywords to categories** [`llm_classify`, `join_tables`] - Classified 22 of 22 rows into 7 labels → Joined 22 + 7 rows on 'category' (left)
5. ✅ **Identify high-priority keywords** [`assign_label`, `assign_label`, `filter_rows`, `select_columns`] - 19 row(s) matched a rule for 'priority' → 5 row(s) matched a rule for 'recommended_target_page' → 6 of 22 rows match
6. ✅ **Export results** [`select_columns`, `export_table`] - Exported 22 rows to outputs/files/run-20261014-185011-eea5c3_keyword_report.csv

### Result
I classified and mapped **22 keywords** to target pages: **6 High**, **13 Medium** and **3 Low** priority. The High-priority terms are led by "buy running shoes" (2,400 searches, transactional) and "best running shoes 2026" (1,900), which both map to /collections/footwear. Other high-priority terms point to /collections/outerwear, /collections/apparel and /collections/activewear. Informational terms such as "how to wash a wool sweater" (2,900) go to /journal/knitwear-guide, and brand/navigational terms go to /pages/help-center. Note that no keyword file was provided, so the default data/samples/keywords.csv was used, and 2 duplicates were removed (Buy Running Shoes, waterproof rain jacket women). The full report is exported to outputs/files/run-20261014-185011-eea5c3_keyword_report.csv.

#### High-priority keywords

| keyword | search_volume | intent | category | recommended_target_page |
|---|---|---|---|---|
| buy running shoes | 2400 | transactional | Footwear | /collections/footwear |
| best running shoes 2026 | 1900 | commercial | Footwear | /collections/footwear |
| waterproof rain jacket women | 1600 | commercial | Outerwear | /collections/outerwear |
| linen shirt men | 1400 | commercial | Apparel | /collections/apparel |
| cheap hiking boots sale | 1100 | transactional | Footwear | /collections/footwear |
| best yoga leggings with pockets | 1000 | commercial | Activewear | /collections/activewear |

#### Keyword report

| keyword | search_volume | intent | category | priority | recommended_target_page |
|---|---|---|---|---|---|
| buy running shoes | 2400 | transactional | Footwear | High | /collections/footwear |
| best running shoes 2026 | 1900 | commercial | Footwear | High | /collections/footwear |
| waterproof rain jacket women | 1600 | commercial | Outerwear | High | /collections/outerwear |
| linen shirt men | 1400 | commercial | Apparel | High | /collections/apparel |
| cheap hiking boots sale | 1100 | transactional | Footwear | High | /collections/footwear |
| best yoga leggings with pockets | 1000 | commercial | Activewear | High | /collections/activewear |
| how to wash a wool sweater | 2900 | informational | Knitwear | Medium | /journal/knitwear-guide |
| what is merino wool | 1300 | informational | Knitwear | Medium | /journal/knitwear-guide |
| how to clean suede chelsea boots | 880 | informational | Footwear | Medium | /journal/footwear-care-and-sizing |
| sports bra high support | 880 | commercial | Activewear | Medium | /collections/activewear |
| merino wool turtleneck | 720 | commercial | Knitwear | Medium | /collections/knitwear |
| chelsea boots discount code | 590 | transactional | Footwear | Medium | /collections/footwear |
| leather belt brown men | 540 | commercial | Accessories | Medium | /collections/accessories |
| northwind store near me | 480 | navigational | Brand & Customer Service | Medium | /pages/help-center |
| hiking boots size guide | 450 | informational | Footwear | Medium | /journal/footwear-care-and-sizing |
| cashmere beanie | 390 | commercial | Accessories | Medium | /collections/accessories |
| rain jacket vs poncho | 320 | commercial | Outerwear | Medium | /collections/outerwear |
| canvas tote bag with zipper | 260 | commercial | Accessories | Medium | /collections/accessories |
| order wool scarf online | 170 | transactional | Accessories | Medium | /collections/accessories |
| northwind return policy | 350 | navigational | Brand & Customer Service | Low | /pages/help-center |
| corduroy overshirt outfit ideas | 230 | informational | Apparel | Low | /journal/apparel-care-and-style |
| northwind apparel login | 210 | navigational | Brand & Customer Service | Low | /pages/help-center |

#### Exported file

outputs/files/run-20261014-185011-eea5c3_keyword_report.csv

**Warnings:**
- No keyword file was given - using the default: data/samples/keywords.csv
- Removed 2 duplicate(s): Buy Running Shoes , waterproof rain jacket women

_Run run-20261014-185011-eea5c3 - 11.2s, LLM calls: 4, tokens: 10477 in / 1130 out_

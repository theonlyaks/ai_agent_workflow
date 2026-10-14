# WF010_excel_test

_What this checks: Tests aggregation and reporting_

**Request:** Which workflows are failing most often?

**Selected Workflow:** WF010 - Workflow Performance Report
**Routing:** Claude tool calling (confidence: high) - User asks which workflows fail most often, which matches the workflow performance report (failure rate analysis).
**Status:** ⚠️ Completed with flags

### Steps Executed
1. ✅ **Load execution logs** [`load_execution_logs`, `compute_column`, `aggregate`] - 309 runs / 1662 step records (9 live runs from this app) → Calculated 'is_failed' = status == 'failed'
2. ✅ **Calculate success/failure rate** [`aggregate`, `compute_column`, `compute_column`] - Calculated 'failure_rate_pct' = failure_rate_pct * 100 → Calculated 'success_rate_pct' = 100 - failure_rate_pct
3. ✅ **Calculate average execution time** [`aggregate`, `join_tables`] - Joined 10 + 10 rows on 'workflow_id' (left)
4. ✅ **Identify frequent errors** [`filter_rows`, `aggregate`] - 23 of 1662 rows match
5. ✅ **Identify slow steps** [`aggregate`, `filter_rows`] - 2 of 56 rows match
6. ⚠️ **Generate recommendations** [`assign_label`, `select_columns`, `llm_generate`] - 3 workflow(s) breach a threshold (failure rate > 10% or average run time > 10000 ms) → Generated recommendations (claude-sonnet-5-5)

### Result
The workflows failing most often are **WF005 Customer Order Status** (**19.4%**, 6 of 31 runs) and **WF003 Vendor File Processing** (**16.1%**, 5 of 31 runs). Both exceed the 10% failure threshold. WF005's main error is a shipment API timeout (4 occurrences) and WF003's main error is unsupported '.pdf' files (3 occurrences). Flag: 3 workflows breach a threshold, the third being WF008 SEO Keyword Classification, which is flagged as slow (average 14,305 ms) with a 9.7% failure rate, all from Claude API rate limiting. Next are WF002, WF007 and WF009 at 6.4% each, all within thresholds.

#### Workflow performance (sorted by failure rate)

| workflow_id | workflow_name | runs | failures | failure_rate_pct | success_rate_pct | avg_duration_ms | max_duration_ms | health |
|---|---|---|---|---|---|---|---|---|
| WF005 | Customer Order Status | 31 | 6 | 19.4 | 80.6 | 1442.73 | 2352 | FLAG: high failure rate |
| WF003 | Vendor File Processing | 31 | 5 | 16.1 | 83.9 | 819.987 | 1429 | FLAG: high failure rate |
| WF008 | SEO Keyword Classification | 31 | 3 | 9.7 | 90.3 | 14304.7 | 23409 | FLAG: slow |
| WF002 | Product Price Validation | 31 | 2 | 6.4 | 93.6 | 740.081 | 1263 | Healthy |
| WF007 | Marketing Campaign Brief | 31 | 2 | 6.4 | 93.6 | 9477.49 | 28521.1 | Healthy |
| WF009 | Employee Task Assignment | 31 | 2 | 6.4 | 93.6 | 3906.58 | 5380.1 | Healthy |
| WF001 | Inventory Restock Check | 31 | 1 | 3.2 | 96.8 | 720.919 | 1156 | Healthy |
| WF004 | Product Description Generator | 31 | 1 | 3.2 | 96.8 | 6931.06 | 13683.9 | Healthy |
| WF006 | Duplicate Product Detection | 31 | 1 | 3.2 | 96.8 | 1549.89 | 2441 | Healthy |
| WF010 | Workflow Performance Report | 30 | 0 | 0 | 100 | 3238.23 | 4339 | Healthy |

#### Most frequent errors

| workflow_id | step | error | occurrences |
|---|---|---|---|
| WF005 | Retrieve shipment information | Shipment API timeout (gave up after 3 attempts) | 4 |
| WF003 | Read file | Unsupported file format '.pdf' | 3 |
| WF008 | Classify search intent | Rate limited by the Claude API (429) after retries | 3 |
| WF002 | Match products by SKU | Vendor price file has no 'sku' column | 2 |
| WF003 | Validate required fields | Required column(s) ['sku'] could not be found | 2 |
| WF005 | Search order data | GET /orders temporarily unavailable (HTTP 503) | 2 |
| WF007 | Validate inputs | Missing required information: campaign goal | 2 |
| WF009 | Select employee | No available employee has the required skills | 2 |
| WF001 | Load inventory | File not found: inventory.csv | 1 |
| WF004 | Create product description | LLM request timed out | 1 |

#### Slow steps

| workflow_id | step | avg_duration_ms | executions |
|---|---|---|---|
| WF008 | Classify search intent | 8162.16 | 31 |
| WF008 | Map keywords to categories | 6176.04 | 28 |

#### Recommendations

- **Recommendations:**

| workflow_id | issue | recommendation | priority |
|---|---|---|---|
| WF005 | Failure rate 19.4% (6 of 31 runs) exceeds the 10% threshold. Main errors: Shipment API timeout after 3 attempts at 'Retrieve shipment information' (4 occurrences) and HTTP 503 on GET /orders at 'Search order data' (2 occurrences). | Add a circuit breaker and exponential backoff with jitter around the shipment and orders API calls. Set explicit timeouts and add a fallback, such as returning order data with a 'shipment info temporarily unavailable' status or serving cached shipment data, so a single dependency outage does not fail the run. Alert on repeated 503s. | high |
| WF003 | Failure rate 16.1% (5 of 31 runs) exceeds the 10% threshold. Errors: unsupported file format '.pdf' at 'Read file' (3 occurrences) and missing required column 'sku' at 'Validate required fields' (2 occurrences). | Add upfront input validation at intake: check the file extension and reject unsupported formats such as .pdf with a clear message to the vendor, or add a supported PDF extraction step if PDFs are expected. Also run a header/schema pre-check for the required 'sku' column before processing, and send actionable feedback to the file submitter. | high |
| WF008 | Average duration 14304.7 ms exceeds the 10000 ms threshold (max 23409 ms). Slow steps: 'Classify search intent' averages 8162.2 ms across 31 executions and 'Map keywords to categories' averages 6176.0 ms across 28. 'Classify search intent' also hit Claude API rate limiting (429) after retries in 3 runs, which accounts for all 3 failures (9.7%, close to the 10% limit). | Batch multiple keywords per Claude request and run classification calls in parallel with a concurrency cap to stay under rate limits. Cache results for repeated keywords and add exponential backoff that honors the Retry-After header. Consider combining or parallelizing the 'Map keywords to categories' step with classification where the data allows. | high |
| WF002 | 2 failures from 'Match products by SKU' because the vendor price file has no 'sku' column. The same missing-column problem appears in WF003. WF002 is currently within thresholds at 6.4%. | Reuse the same schema pre-validation as WF003 (required-column check before processing) so files without a 'sku' column are rejected early with a clear error message. A shared validation step would prevent the same input problem in both workflows. | medium |
| WF007 | Average duration 9477.5 ms is just under the 10000 ms threshold, but max duration is 28521.1 ms. 2 failures came from 'Validate inputs' with missing required information: campaign goal. The data does not identify which steps cause the long runs. | Make 'campaign goal' a required field at submission time so it is caught before the run starts. Add per-step timing to identify what drives the long-tail runs, since no slow-step data was provided for this workflow. | low |


**Flags:**
- 3 workflow(s) breach a threshold (failure rate > 10% or average run time > 10000 ms)

_Run run-20261014-185033-4b9a5d - 13.8s, LLM calls: 3, tokens: 11855 in / 1480 out_

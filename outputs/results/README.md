# Test run results

_Generated 2026-10-14 18:51 - LLM: claude-sonnet-5-5_

| Scenario | Request | Expected workflow | Selected workflow | Status | Follow-up answers | Time |
|---|---|---|---|---|---|---|
| [WF001_excel_test](WF001_excel_test.md) | Which products need restocking? | WF001 | WF001 | ✅ Completed | 0 | 4.6s |
| [WF002_excel_test](WF002_excel_test.md) | Find products where vendor price differs by more than 10%. | WF002 | WF002 | ⚠️ Completed with flags | 0 | 12.1s |
| [WF003_excel_test](WF003_excel_test.md) | Process this vendor spreadsheet and show invalid rows. | WF003 | WF003 | ✅ Completed | 0 | 4.6s |
| [WF004_excel_test](WF004_excel_test.md) | Generate SEO content for this product. | WF004 | WF004 | ✅ Completed | 1 | 20.0s |
| [WF005_excel_test](WF005_excel_test.md) | Where is order ORD-1001? | WF005 | WF005 | ✅ Completed | 0 | 3.9s |
| [WF006_excel_test](WF006_excel_test.md) | Find likely duplicate products in the catalog. | WF006 | WF006 | ✅ Completed | 0 | 4.3s |
| [WF007_excel_test](WF007_excel_test.md) | Create a campaign brief for the new collection. | WF007 | WF007 | ✅ Completed | 1 | 35.9s |
| [WF008_excel_test](WF008_excel_test.md) | Classify these keywords and map them to pages. | WF008 | WF008 | ✅ Completed | 0 | 11.2s |
| [WF009_excel_test](WF009_excel_test.md) | Assign this urgent task to the best available developer. | WF009 | WF009 | ✅ Completed | 1 | 11.1s |
| [WF010_excel_test](WF010_excel_test.md) | Which workflows are failing most often? | WF010 | WF010 | ⚠️ Completed with flags | 0 | 13.8s |
| [WF005_unknown_order_then_email](WF005_unknown_order_then_email.md) | Where is order ORD-9999? | WF005 | WF005 | ✅ Completed | 1 | 6.4s |
| [WF005_invalid_identifier](WF005_invalid_identifier.md) | What's the status of my order 12345? | WF005 | WF005 | ✅ Completed | 1 | 5.7s |
| [WF002_custom_threshold](WF002_custom_threshold.md) | Validate our product prices against the vendor list and flag anything more than 20% off. | WF002 | WF002 | ⚠️ Completed with flags | 0 | 4.4s |
| [WF001_global_threshold](WF001_global_threshold.md) | Which products have fewer than 10 units in stock and need reordering? | WF001 | WF001 | ✅ Completed | 0 | 6.3s |
| [WF004_sku_lookup](WF004_sku_lookup.md) | Write SEO content for SKU-2004 | WF004 | WF004 | ✅ Completed | 0 | 12.5s |
| [WF009_escalation](WF009_escalation.md) | Urgent: assign task T-204 (iOS checkout crash) to the best available developer. | WF009 | WF009 | 🔺 Escalated | 0 | 6.9s |
| [WF003_missing_file](WF003_missing_file.md) | Process the vendor file [Attached file: data/uploads/does_not_exist.xlsx] | WF003 | WF003 | ❌ Failed | 0 | 1.6s |
| [router_ambiguous_request](router_ambiguous_request.md) | Can you help me with something? | - | WF001 | ✅ Completed | 1 | 6.4s |
| [router_out_of_scope](router_out_of_scope.md) | What's the weather in Paris tomorrow? | - | - | ❓ Waiting for your input | 0 | 0.0s |

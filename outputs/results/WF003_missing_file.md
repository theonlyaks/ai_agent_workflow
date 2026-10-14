# WF003_missing_file

_What this checks: Error handling: missing file fails gracefully with a clear message_

**Request:** Process the vendor file [Attached file: data/uploads/does_not_exist.xlsx]

**Selected Workflow:** WF003 - Vendor File Processing
**Routing:** Claude tool calling (confidence: high) - User asked to process an attached vendor file.
**Status:** ❌ Failed

### Steps Executed
1. ❌ **Read file** [`read_table`] - File not found: data/uploads/does_not_exist.xlsx
2. ⏭️ **Detect columns** [-]
3. ⏭️ **Normalize column names** [-]
4. ⏭️ **Validate required fields** [-]
5. ⏭️ **Identify invalid rows** [-]
6. ⏭️ **Produce cleaned dataset** [-]

**Error:** File not found: data/uploads/does_not_exist.xlsx

### Result
Vendor File Processing could not be completed: File not found: data/uploads/does_not_exist.xlsx

_Run run-20261014-185129-445652 - 1.6s, LLM calls: 1, tokens: 4641 in / 127 out_

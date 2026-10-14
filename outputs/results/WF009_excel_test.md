# WF009_excel_test

_What this checks: Tests ranking and decision logic_

**Request:** Assign this urgent task to the best available developer.

**Selected Workflow:** WF009 - Employee Task Assignment
**Routing:** Claude tool calling (confidence: high) - User asks to assign an urgent task to the best available developer.
**Status:** ✅ Completed

**Conversation:**
> **User:** Assign this urgent task to the best available developer.
> **Assistant:** Which task should I assign? Reply with a backlog task ID, or describe the work (skills needed, effort and deadline).
> 
> Available options:
> - T-201 | Fix payment API timeouts under peak load | urgent | 2026-10-16
> - T-202 | Build the new product filter UI | high | 2026-10-24
> - T-203 | Move CI pipelines to GitHub Actions | medium | 2026-11-05
> - T-204 | iOS app crashes on checkout | urgent | 2026-10-15
> - T-205 | Nightly sales data pipeline is failing | high | 2026-10-18
> **User:** T-201 - the payment API timeouts

### Steps Executed
1. ✅ **Understand task requirements** [`read_table`, `validate_fields`, `read_table`, `llm_generate`] - Loaded 5 rows x 6 columns from tasks.csv → All required fields present (5 provided) → Loaded 9 rows x 7 columns from employees.csv → Generated task_id, title, required_skills, estimated_hours, priority, deadline (claude-sonnet-5-5)
2. ✅ **Compare employee skills** [`filter_rows`, `skill_match`] - 6 of 9 rows match → Required: fastapi, postgresql, python. 1 of 6 have all skills
3. ✅ **Check current workload** [`compute_column`, `compute_column`, `compute_column`] - Calculated 'available_hours' = capacity_hours - current_workload_hours → Calculated 'capacity_score' = available_hours / capacity_hours → Calculated 'is_available' = availability == 'available'
4. ✅ **Rank candidates** [`rank_rows`, `select_columns`] - Weights: skill_match=0.5, capacity_score=0.5
5. ✅ **Select employee** [`select_best`] - 2 eligible candidate(s); selected rank #1
6. ✅ **Generate assignment summary** [`llm_generate`, `build_record`] - Generated summary, reasoning (claude-sonnet-5-5)

### Result
Assign **T-201 (Fix payment API timeouts under peak load)** to **Aarav Mehta** (E01, Senior Backend Developer). It is urgent, due **2026-10-16**, with an estimated effort of **6 hours**. He scored **0.65** and is the only candidate with a full skill match (python, fastapi, postgresql). He has **12 available hours**, which covers the estimate. The runner-up, Sofia Martins, scored 0.61 but lacks fastapi, though she has more free hours (22). No flags or warnings were raised.

#### Recommended assignment

- **Recommended employee:** Aarav Mehta
- **Employee id:** E01
- **Role:** Senior Backend Developer
- **Task:** Fix payment API timeouts under peak load
- **Task id:** T-201
- **Priority:** urgent
- **Deadline:** 2026-10-16
- **Estimated hours:** 6
- **Matched skills:** fastapi, postgresql, python
- **Available hours:** 12
- **Score:** 0.65
- **Reasoning:** Aarav Mehta ranked first with a score of 0.65. He has a full skill match (1.0), covering all three required skills: python, fastapi and postgresql, with no missing skills. He is available, with 12 available hours (40 capacity minus 28 current workload), which covers the 6 estimated hours. The alternative, Sofia Martins (E02), scored 0.61 with a skill match of 0.67; she lacks fastapi, though she has more available hours (22) and a higher capacity score (0.55 vs 0.3). Aarav was preferred because he meets every required skill, which outweighed Sofia's greater free capacity.
- **Summary:** Task T-201 (Fix payment API timeouts under peak load) is assigned to Aarav Mehta, Senior Backend Developer (E01). The task is urgent priority with a deadline of 2026-10-16 and an estimated effort of 6 hours.

#### Candidate ranking

| rank | name | role | skill_match | matched_skills | missing_skills | available_hours | availability | score |
|---|---|---|---|---|---|---|---|---|
| 1 | Aarav Mehta | Senior Backend Developer | 1 | fastapi, postgresql, python | - | 12 | available | 0.65 |
| 2 | Sofia Martins | Backend Developer | 0.67 | postgresql, python | fastapi | 22 | available | 0.61 |
| 3 | Emma Rossi | Mobile Developer | 0 | - | fastapi, postgresql, python | 30 | on_leave | 0.375 |
| 4 | Fatima Khan | Full Stack Developer | 0.67 | fastapi, python | postgresql | 2 | available | 0.36 |
| 5 | Liam Chen | Frontend Developer | 0 | - | fastapi, postgresql, python | 20 | available | 0.25 |
| 6 | Lucas Silva | Frontend Developer | 0 | - | fastapi, postgresql, python | 4 | available | 0.05 |

#### Task requirements

- **Task id:** T-201
- **Title:** Fix payment API timeouts under peak load
- **Required skills:**
  - python
  - fastapi
  - postgresql
- **Estimated hours:** 6
- **Priority:** urgent
- **Deadline:** 2026-10-16

_Run run-20261014-185022-531ad2 - 11.1s, LLM calls: 5, tokens: 10905 in / 764 out_

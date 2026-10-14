# WF009_escalation

_What this checks: Only the on-leave employee has the skill -> escalation_

**Request:** Urgent: assign task T-204 (iOS checkout crash) to the best available developer.

**Selected Workflow:** WF009 - Employee Task Assignment
**Routing:** Claude tool calling (confidence: high) - Manager asks to assign a backlog task to the best available developer.
**Status:** 🔺 Escalated

### Steps Executed
1. ✅ **Understand task requirements** [`read_table`, `validate_fields`, `read_table`, `llm_generate`] - Loaded 5 rows x 6 columns from tasks.csv → All required fields present (5 provided) → Loaded 9 rows x 7 columns from employees.csv → Generated task_id, title, required_skills, estimated_hours, priority, deadline (claude-sonnet-5-5)
2. ✅ **Compare employee skills** [`filter_rows`, `skill_match`] - 6 of 9 rows match → Required: swift. 1 of 6 have all skills
3. ✅ **Check current workload** [`compute_column`, `compute_column`, `compute_column`] - Calculated 'available_hours' = capacity_hours - current_workload_hours → Calculated 'capacity_score' = available_hours / capacity_hours → Calculated 'is_available' = availability == 'available'
4. ✅ **Rank candidates** [`rank_rows`, `select_columns`] - Weights: skill_match=0.5, capacity_score=0.5
5. 🔺 **Select employee** [`select_best`] - No available employee has the required skills and enough free capacity for this task - escalated to the engineering manager for a decision (re-prioritise work, extend the deadline or bring in outside help).
6. ⏭️ **Generate assignment summary** [-]

### Result
I couldn't assign T-204 (iOS app crashes on checkout; urgent, 8 estimated hours, due 2026-10-15) because no available employee has both the required skill (swift) and enough free capacity, so it was **escalated to the engineering manager**. Emma Rossi (Mobile Developer) is the only candidate with swift and ranked first (score 0.875, 30 available hours), but she is marked **on leave**. The other five candidates are available but all lack swift, with Sofia Martins (22 hours) the highest of them. The manager will need to decide whether to re-prioritise work, extend the deadline or bring in outside help.

#### Escalation

No available employee has the required skills and enough free capacity for this task - escalated to the engineering manager for a decision (re-prioritise work, extend the deadline or bring in outside help).

#### Candidate ranking

| rank | name | role | skill_match | matched_skills | missing_skills | available_hours | availability | score |
|---|---|---|---|---|---|---|---|---|
| 1 | Emma Rossi | Mobile Developer | 1 | swift | - | 30 | on_leave | 0.875 |
| 2 | Sofia Martins | Backend Developer | 0 | - | swift | 22 | available | 0.275 |
| 3 | Liam Chen | Frontend Developer | 0 | - | swift | 20 | available | 0.25 |
| 4 | Aarav Mehta | Senior Backend Developer | 0 | - | swift | 12 | available | 0.15 |
| 5 | Lucas Silva | Frontend Developer | 0 | - | swift | 4 | available | 0.05 |
| 6 | Fatima Khan | Full Stack Developer | 0 | - | swift | 2 | available | 0.025 |

#### Task requirements

- **Task id:** T-204
- **Title:** iOS app crashes on checkout
- **Required skills:**
  - swift
- **Estimated hours:** 8
- **Priority:** urgent
- **Deadline:** 2026-10-15

_Run run-20261014-185122-6e2ece - 6.9s, LLM calls: 3, tokens: 7677 in / 451 out_

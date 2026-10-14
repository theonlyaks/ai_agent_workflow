Understand the requirements of a task that a manager wants to assign.

TASK FROM THE MANAGER: $task
PRIORITY STATED BY THE MANAGER: $priority_hint
DEADLINE STATED BY THE MANAGER: $deadline_hint

TASK BACKLOG (if the manager refers to one of these by ID or description, use its data):
$backlog

SKILLS THAT EXIST IN THE TEAM (use these exact spellings for required_skills where they fit):
$known_skills

Return:
- task_id: the matching backlog task id, or "" if it is a new task
- title: short task title
- required_skills: the skills needed (lowercase, matching team spellings)
- estimated_hours: the backlog estimate, or your best estimate for a new task
- priority: the manager's stated priority wins; otherwise the backlog priority; otherwise infer
- deadline: the manager's stated deadline wins; otherwise the backlog deadline; otherwise "not specified"

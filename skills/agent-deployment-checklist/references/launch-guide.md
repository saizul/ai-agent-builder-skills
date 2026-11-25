# Launch guide

## Severity

- **BLOCKER**: launching without it can harm users, leak data, lose money, or leave you unable
  to stop the agent. Never accepted with sign-off.
- **MAJOR**: launching without it makes problems likely or invisible. Acceptable for a small,
  watched pilot with a named owner and a due date.
- **MINOR**: good practice; track as a follow-up.

## Pilot plan

1. Small traffic share (5-10%) or one segment (one channel, one language, logged-in users).
2. Business hours first, with handover staff aware of the pilot.
3. Daily: dashboard check (volume, handover, errors, latency, cost) and 10-20 sampled conversations.
4. Weekly: `conversation-log-analysis`, new eval cases from failures, re-run evals.
5. Expansion criteria written in advance (e.g. two consecutive weeks meeting KPI targets, no
   BLOCKER incidents), and decided by the named owner.

## Kill switch and rollback

- Feature flag or routing rule that sends all traffic to the previous flow (human queue, form).
- Per-tool disable switch for write actions.
- Versioned prompt, tool definitions and model configuration; rollback is a config change, not a deploy.
- Test both before launch and record the time it took.

## Incident playbook (minimum)

1. Detect: alert or report. 2. Decide: owner can disable the agent or a tool without approval.
3. Contain: disable, roll back, block abusive users. 4. Communicate: support staff, affected users
if needed, data protection owner for personal data incidents. 5. Learn: root cause, new eval
case, checklist item if a control was missing.

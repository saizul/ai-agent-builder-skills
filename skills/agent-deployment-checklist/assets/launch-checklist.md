# Agent launch checklist: <agent name> <version>

<!-- Mark items: [x] done, [ ] open, [~] not applicable (add "(n/a: reason)").
     Add evidence after "-- evidence:" (link to doc, dashboard, eval run, ticket).
     Score it: python3 scripts/readiness_check.py launch-checklist.md -->

## Scope and ownership

- [ ] [BLOCKER] Agent spec signed off by the business owner (scope, out-of-scope, handover, KPIs) -- evidence: <link>
- [ ] [BLOCKER] Named owners for prompt, knowledge base, tools and on-call -- evidence: <link>
- [ ] [MAJOR] Users are told they are talking to an AI assistant, and how to reach a person
- [ ] [MINOR] Internal FAQ for support staff about what the agent does and does not do

## Quality

- [ ] [BLOCKER] Eval set covers every in-scope task, out-of-scope, handover and safety cases -- evidence: <link>
- [ ] [BLOCKER] Eval pass rate meets the agreed bar on the release candidate; no regressions -- evidence: <results.json>
- [ ] [MAJOR] Retrieval smoke test passes (expected source in top 5 for 90%+ of questions)
- [ ] [MAJOR] Tested in every channel and language that will be live
- [ ] [MINOR] Prompt, tool definitions and model version recorded for this release

## Safety and privacy

- [ ] [BLOCKER] Write actions require confirmation enforced in code; limits configured -- evidence: <link>
- [ ] [BLOCKER] Tools authorise per user; the agent cannot access other customers' data -- evidence: <link>
- [ ] [BLOCKER] PII redaction for logs/analytics in place; retention period configured -- evidence: <link>
- [ ] [MAJOR] Untrusted content scanned for prompt injection; flagged items quarantined
- [ ] [MAJOR] Data processing terms and data region with the LLM provider confirmed by the data owner
- [ ] [MAJOR] No secrets in prompts, tool results or logs (scan done)
- [ ] [MINOR] Output link/domain allowlist for channels that render links

## Handover

- [ ] [BLOCKER] Handover path tested end to end, including out-of-hours behaviour -- evidence: <link>
- [ ] [MAJOR] Humans receive summary, intent and collected fields (no repeated questions)
- [ ] [MAJOR] Staffing for expected handover volume during the pilot

## Reliability and cost

- [ ] [BLOCKER] Kill switch / feature flag to turn the agent off within minutes, tested -- evidence: <link>
- [ ] [BLOCKER] Rollback to previous prompt/model/tool version is documented and tested -- evidence: <link>
- [ ] [MAJOR] Timeouts, retries and friendly fallback message for LLM provider and tool outages
- [ ] [MAJOR] Rate limits per user/IP and a monthly spend cap or alert
- [ ] [MAJOR] Cost estimate reviewed against budget for expected and 2x traffic
- [ ] [MINOR] Load test of tools/backends at expected peak

## Monitoring

- [ ] [BLOCKER] Conversation logging (redacted) with conversation IDs, tool calls and errors -- evidence: <link>
- [ ] [MAJOR] Dashboard: volume, handover rate, failure turns, tool errors, latency, cost per day
- [ ] [MAJOR] Alerts on error rate, latency, spend and handover spikes, routed to on-call
- [ ] [MAJOR] Weekly review scheduled (log analysis + sampled conversations + new eval cases)
- [ ] [MINOR] User feedback capture (thumbs, CSAT) wired to the dashboard

## Rollout

- [ ] [BLOCKER] Pilot scope defined (traffic share, hours, segments) with go/no-go criteria for expansion
- [ ] [MAJOR] Incident playbook: who decides, how to disable a tool, how to notify users and staff
- [ ] [MINOR] Changelog / release notes for stakeholders

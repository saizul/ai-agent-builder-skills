# Agent spec: Returns assistant

Version: 0.2 | Owner: Head of Customer Service | Tech lead: Platform team | Last updated: 2026-11-20

## 1. Business goal

Answer order-status and returns questions on web chat so that the support team handles 40% fewer
tickets without lowering customer satisfaction.

## 2. Users and channels

- Who: online shop customers, English and German, about 600 chats per day
- Channels: web chat on the shop website
- Hours: 24/7; handover only during support hours 08:00-20:00

## 3. In scope (tasks)

| # | Task | Example request | Done when |
| --- | --- | --- | --- |
| 1 | Order status | "Where is my order ORD-104233?" | status and ETA given from the order system |
| 2 | Return eligibility | "Can I still return my shoes?" | policy answer with the order's dates |
| 3 | Create return | "Please start a return" | return created after confirmation, label sent |

## 4. Out of scope

- Refunds above 100 EUR, damaged-item claims, account changes
- Legal questions and complaints about staff

## 5. Tools and data access

| Tool | Purpose | Access | Confirmation required | Owner |
| --- | --- | --- | --- | --- |
| lookup_order | read order status by order number + email | read | no | Ops |
| check_return_policy | eligibility for an order | read | no | Ops |
| create_return | open a return for an eligible order | write | yes, user confirms summary | Ops |

## 6. Handover rules

| Trigger | Handover to | Channel | Information passed |
| --- | --- | --- | --- |
| User asks for a human | Tier 1 queue | live chat transfer | summary, order number, intent |
| Refund above 100 EUR | Billing team | ticket | summary, order, amount |
| Two failed attempts | Tier 1 queue | live chat transfer | summary and transcript link |

## 7. Guardrails and policies

- Verify order number + email before showing order details
- Never promise refunds; redact PII before logging; 30-day log retention

## 8. KPIs

| KPI | Baseline | Target | How measured |
| --- | --- | --- | --- |
| Containment rate | 0% | 40% by week 8 | resolved flag in conversation logs |
| CSAT | 4.3 human | at least 4.2 | post-chat survey |
| Cost per resolved conversation | 3.10 EUR human | below 0.30 EUR | LLM + infra cost / resolved |

## 9. Evaluation plan

- 30 test conversations per task including out-of-scope and handover cases
- Pass bar 95% on policy tags, 90% overall

## 10. Risks and open questions

- Order API latency at peak; mitigation: timeout message and retry

## 11. Rollout

- Pilot on 10% of web chat traffic for two weeks; kill switch via feature flag

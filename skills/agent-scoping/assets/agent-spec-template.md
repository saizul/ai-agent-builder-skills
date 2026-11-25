# Agent spec: <agent name>

<!-- Fill every section. Replace each <placeholder>. Delete these comments when done.
     Check it with: python3 scripts/spec_lint.py agent-spec.md -->

Version: <0.1> | Owner: <business owner> | Tech lead: <name> | Last updated: <YYYY-MM-DD>

## 1. Business goal

<One paragraph: which business process this agent takes over or assists, why now, and what
"good" looks like in money, time or quality. Example: "Answer order-status and returns
questions on web chat so the support team handles 40% fewer tickets, without lowering CSAT.">

## 2. Users and channels

- Who: <customers / internal staff / partners>, <languages>, <volume per day>
- Channels: <web chat / email / WhatsApp / internal tool / API>
- Hours: <24/7, or business hours with after-hours behaviour>

## 3. In scope (tasks)

| # | Task | Example request | Done when |
| --- | --- | --- | --- |
| 1 | <Answer order status> | <"Where is my order 1234?"> | <status + ETA given from the order system> |
| 2 | <task> | <example> | <definition of done> |

## 4. Out of scope

- <Things the agent must refuse or hand over: legal advice, price negotiation, account deletion ...>
- <Topics it must not discuss>

## 5. Tools and data access

| Tool | Purpose | Access | Confirmation required | Owner |
| --- | --- | --- | --- | --- |
| <lookup_order> | <read order status by order number + email> | <read> | <no> | <ops team> |
| <create_return> | <open a return for an eligible order> | <write> | <yes, user confirms summary first> | <ops team> |

Data the agent may see: <fields>. Data it must never see or store: <card numbers, IDs ...>.

## 6. Handover rules

| Trigger | Handover to | Channel | Information passed |
| --- | --- | --- | --- |
| <User asks for a human> | <Tier 1 support queue> | <live chat transfer> | <summary, order number, intent> |
| <Refund above <amount>> | <Billing team> | <ticket> | <summary, order, amount> |
| <Two failed attempts to answer> | <Tier 1 support queue> | <live chat transfer> | <summary + transcript link> |

Out of hours: <what the agent says and does when nobody is available>.

## 7. Guardrails and policies

- <Never promise refunds or delivery dates the systems do not confirm>
- <Verify identity with order number + email before showing order details>
- <PII handling: redact before logging; retention <30 days>>
- <Regulatory or brand rules>

## 8. KPIs

| KPI | Baseline | Target | How measured |
| --- | --- | --- | --- |
| <Containment rate (resolved without human)> | <0%> | <40% by week 8> | <conversation logs, resolved flag> |
| <Handover rate> | <n/a> | <below 30%> | <handover events / conversations> |
| <CSAT on agent conversations> | <4.3/5 human> | <at least 4.2/5> | <post-chat survey> |
| <Cost per resolved conversation> | <human cost> | <below <amount>> | <LLM + infra cost / resolved> |

## 9. Evaluation plan

- <30+ test conversations per in-scope task, including edge cases and out-of-scope requests>
- <Pass bar: 95% on policy checks, 90% overall before pilot>
- <Weekly review of 50 sampled live conversations>

## 10. Risks and open questions

- <Risk: order system API latency above 3 s at peak. Mitigation: cache, timeout message>
- <Open question: can returns be created for marketplace orders?>

## 11. Rollout

- <Pilot: 10% of web chat traffic, business hours, 2 weeks>
- <Go/no-go owner and criteria; kill switch: <how to turn the agent off>>

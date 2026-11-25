# Scoping patterns

## Automate, assist or keep human

| Step property | Automate | Assist (draft + approve) | Keep human |
| --- | --- | --- | --- |
| Answer exists in a system or document | yes | | |
| Reversible action, low value | yes (confirm) | | |
| Money, contracts, account security | | yes | if high value |
| Needs empathy / complaint / legal threat | | | yes |
| Judgement with no written rule | | yes, after rules are written | yes, until then |
| Rare (< 1% of volume) | | | yes, hand over |

## Common agent shapes

- **FAQ + lookup assistant**: retrieval over docs + read-only tools. Lowest risk; start here.
- **Transactional assistant**: adds write tools (book, cancel, create return). Confirmation step
  per action; idempotent tools; audit log.
- **Back-office worker**: processes documents or queues (invoices, emails) without a live user.
  Needs a review queue, confidence thresholds and batch metrics instead of CSAT.
- **Copilot for staff**: drafts for employees who approve. Easiest to launch; measure time saved
  and edit distance of drafts.

## Effort and risk checklist

- Number of tools, and how many write data
- Systems without an API (screen scraping or manual export = high risk)
- Languages and channels
- Size and freshness of the knowledge base
- Regulated data
- Evaluation set size needed (rule of thumb: 20-50 cases per in-scope task)
- Who maintains prompts, knowledge and evals after launch

## Handover design

- Pass a summary, the detected intent, collected fields and a transcript link, so the human does
  not ask the same questions again.
- Tell the user what happens next and when ("A colleague will reply by email within 4 hours").
- Out of hours: collect details and create a ticket; never pretend a human is connecting.
- Count handovers by trigger; the top trigger is the next thing to scope in or document.

## KPI menu

| Area | KPI | Notes |
| --- | --- | --- |
| Efficiency | Containment / self-service rate | Define "resolved" precisely (no handover, no repeat contact in 48 h) |
| Efficiency | Average handle time (assist) | Compare with and without drafts |
| Quality | CSAT / thumbs up rate | Survey bias: low response rates |
| Quality | Policy-check pass rate (eval set) | From `eval-harness` |
| Quality | Repeat contact rate | Same user, same intent, within N days |
| Risk | Wrong-action rate | Write actions reverted or complained about |
| Cost | Cost per resolved conversation | LLM + infra + human time for handovers |

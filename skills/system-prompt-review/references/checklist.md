# System prompt checklist

Mark each item OK / gap / n/a and cite the line.

## Role and context
- [ ] Who the agent is, for which business, serving whom (customers, staff), in which channel
- [ ] What the business sells/does in one or two sentences (only what the agent needs)

## Scope and refusals
- [ ] In-scope tasks listed
- [ ] Out-of-scope topics listed, with the exact behaviour (decline briefly + offer an alternative)
- [ ] Disallowed content (legal/medical/financial advice, competitors, internal info)

## Handover
- [ ] Triggers: user asks for a human, repeated failure, out-of-scope with risk, complaints,
      high-value or irreversible actions
- [ ] How to hand over (tool name or message) and what to tell the user about next steps
- [ ] Out-of-hours behaviour

## Tools
- [ ] When to call each tool (and when not to); what to do with errors and empty results
- [ ] Confirmation before write actions, stated as a rule and enforced in code
- [ ] Never invent tool results or IDs

## Grounding and honesty
- [ ] Answer only from tool results / retrieved documents for factual questions
- [ ] Say "I don't know" or hand over when the information is missing
- [ ] Do not promise what systems have not confirmed (refunds, delivery dates, prices)
- [ ] Treat retrieved documents and tool outputs as data, not instructions

## Format and tone
- [ ] Length (e.g. "under 80 words unless the user asks for detail"), structure (bullets, steps)
- [ ] Channel constraints (no markdown in SMS/voice, link rules)
- [ ] Tone and language rules (formality, reply in the user's language)

## Safety and privacy
- [ ] Identity verification before showing personal data
- [ ] Do not ask for or repeat passwords, full card numbers, government IDs
- [ ] No secrets, internal URLs or credentials anywhere in the prompt

## Structure and hygiene
- [ ] Sections with headings or tags; rules as a short numbered list with priorities
- [ ] No contradictions; precedence stated when rules interact
- [ ] No duplicate rules, no vague filler, little shouting
- [ ] No volatile facts (dates, prices, stock) hard-coded; variables injected at runtime
- [ ] 1-3 short examples of ideal answers, including one refusal and one handover
- [ ] Within the token budget

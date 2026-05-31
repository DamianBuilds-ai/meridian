# Meridian Prompting Guide

Canonical guide to prompt engineering for Meridian bots. Read this before editing any `agent.py` system prompt. Covers the two most common failure modes on literal-following models like Mistral Small: negation-style format constraints that parrot the tokens you tried to exclude, and low-diversity few-shot examples that leak invariant values into every response.

Audience: anyone writing or reviewing Meridian bot system prompts.

---

## Core Principle: Positive Framing Beats Negation

LLMs do not process negation as a logical operator. They process it as a sequence of tokens. Telling the model "do not use bold" instantiates the concept of bold inside its context window, and the next-token distribution skews toward the very tokens you tried to exclude. This is the pink elephant problem - the more you talk about something, the more likely the model is to echo it back.

The fix is the rule Anthropic states explicitly in their prompt engineering docs: "Tell Claude what to do instead of what not to do." The same rule applies to every model family, but it matters more for literal-following models like Mistral Small.

The arxiv paper `2503.22395` ("Negation: A Pink Elephant in the LLMs' Room?", March 2025) measured this directly across Mistral Nemo 12B, Mistral Small 22B, and Mistral Large 123B. Negation in instructions produced measurable accuracy drops; the gap narrowed with scale but did not disappear. Mistral Small was the most affected of the Mistral family for its size.

```text
# BEFORE - parrots the banned tokens
BANNED: **bold** *italic* `code` # headers
```

```text
# AFTER - positive directive with reason, wrapped in semantic XML
<output_format>
Replies go to Telegram as plain text. Use ordinary words, numbers, and
punctuation. Asterisks and underscores around words render as literal
symbols rather than formatting, which clutters the message.
</output_format>
```

The AFTER version never names the banned tokens. The model has a positive policy ("words, numbers, punctuation") plus the consequence that motivates it. Per Anthropic: "Claude is smart enough to generalize from the explanation."

---

## Few-Shot Examples: Structure Templates, Not Value Templates

Few-shot examples are the most reliable way to steer model output. They are also the most reliable way to leak unintended invariants into every response.

When you show ONE example with one set of values, the model treats those values as part of the structural template. For example, a task-manager bot that showed only `add task: call supplier -> Task added: call supplier` would echo "call supplier" into replies for completely different task inputs. The model had no signal that the text should vary with user input, because every example it saw used the same phrase.

Rules for few-shot examples in Meridian bots:

1. **Always provide 3 or more examples.** Anthropic recommends 3-5; PromptHub research shows gains plateau after 2-5. Below 3, every value in the example is at risk of being treated as constant.
2. **Vary the values along every dimension the user controls.** If the user supplies a number, the number must differ in every example. If the user supplies an activity, the activity must differ. If the user supplies a phrasing, the phrasing must differ.
3. **Use `Input:` and `Output:` labels inside an `<examples>...</examples>` XML block.** Per Anthropic, wrap examples in `<example>` tags (multiple in `<examples>`) so the model can distinguish them from instructions. Per the OpenAI developer community, explicit labels prevent example values from being mistaken for the actual user message.
4. **Every example output must itself comply with every rule in the prompt.** Demonstration beats description for LLMs - if your rules say "no markdown" and your example uses markdown, the example wins. Audit each example against the rules block before shipping.

```text
<examples>
Input: add task: send Q3 invoice by Friday
Output: Task added: send Q3 invoice by Friday.

Input: remind me to call the supplier tomorrow at 9am
Output: Reminder set: call the supplier, tomorrow at 9am.

Input: mark task 14 done
Output: Task 14 marked complete.
</examples>
```

Three distinct task types (create, remind, update). Three distinct input phrasings. Every output is plain text, matching the format rules above. The model now has to abstract the transformation pattern rather than memorise a single phrase.

---

## Format Constraints

Specify format positively. Wrap the directive in semantic XML so the model treats it as a scoped policy rather than a free-floating mention. State the constraint as what the model should produce, and add a one-sentence reason - per Anthropic, the model generalises better when it understands why.

```text
<output_format>
Your reply is sent to Telegram as plain text. Use only standard words,
numbers, and punctuation - the kind of text that survives being
copy-pasted into a chat box. Keep the response under two sentences.
</output_format>
```

What this avoids:

- No list of banned tokens by name. The words "bold", "italic", "asterisk", "underscore" never appear in the prompt context, so the model is not seeded with them.
- No negation. Every clause is a positive policy.
- Length cap stated positively ("under two sentences") rather than as a negative ("don't be verbose").

When a length cap or behavioural cap is needed, swap the negation for the substitute behaviour:

```text
BAD:  "Don't be verbose"          GOOD: "Respond in 1-2 sentences."
BAD:  "Don't use bullet points"   GOOD: "Respond in flowing prose paragraphs."
BAD:  "Don't ask follow-ups"      GOOD: "End your response after the answer."
```

Every "don't X" becomes "do Y" where Y excludes X as a side effect.

---

## Mistral-Specific Notes

Meridian's default brain is Mistral Small 4 (`mistral-small-2603`). The patterns in this doc matter more for Mistral than for Claude or GPT-4, for three compounding reasons.

**Mistral Small follows instructions literally.** From the official Mistral-Small-3.2-24B-Instruct-2506 HuggingFace model card: "Small-3.2 will follow your instructions down to the last letter!" Combined with the recommended `temperature=0.15`, the model has very little stochastic variation - whatever token sequence has highest local probability wins. If you mention `**bold**` by name in the prompt, that sequence has high local probability after seeing "BANNED: " and the model emits it.

**Negation is a documented weak point.** The arxiv 2503.22395 study found Mistral Small was the most negation-sensitive of the Mistral family for its size. The instruction-following metric improved substantially in Small 3.2 (IFEval 82.75 -> 84.78), which makes the model more precise at mirroring format specs - great for positive specs, brutal for negative ones.

**Few-shot examples are interpreted strictly.** Value-leakage risk is higher on Mistral Small than on Claude or GPT-4 because the model treats demonstrated values as part of the structural template by default. The diversity rule (3 or more examples, varied values) is mandatory for Mistral bots, not optional.

**XML tags are well-handled.** Mistral's own prompting guide recommends "Markdown and/or XML-style tags" as "ideal because they are readable and easy for humans to scan." Wrap rules in `<output_format>`, examples in `<examples>`, routing in `<tool_routing>`. The model treats tagged sections as scoped policies.

---

## Checklist Before Shipping a Prompt

Read top-to-bottom after the last edit. Each item corresponds to a common failure mode on literal-following models.

1. Does every example output comply with every rule in the prompt? (Demo beats description. If the rules ban asterisks and an example uses asterisks, the example wins.)
2. Do examples use 3 or more diverse values across every variable slot? (Numbers, entities, phrasings should all vary.)
3. Are any tokens listed by name in a banned or forbidden list? (If yes, rewrite as a positive directive. The token enters the model's context regardless of what you said around it.)
4. Are there any invariant strings across examples - same number, same name, same phrase? (If yes, vary them.)
5. Are format constraints stated positively as what to produce, not what to avoid?
6. Are examples wrapped in `<examples>` with `Input:` and `Output:` labels?
7. Is each rule paired with a one-sentence reason? (Optional but recommended for literal-following models.)
8. Has the prompt been read top-to-bottom by a human after the last edit? (Catches accidental contradictions between rules and examples.)

---

## Worked Examples

### Example bot: positively-framed format constraints (TaskBot)

Symptom: a task-manager bot's replies included raw markdown tokens as literal text - for example, "Task added: **send invoice**" rendered in Telegram as "Task added: **send invoice**" with visible asterisks. The post-response sanitizer only stripped balanced pairs; unpaired tokens survived.

Root cause: the system prompt listed the banned tokens by name. Once `**bold**` appeared in the model's context, the literal-following behaviour of Mistral Small treated those tokens as legitimate output candidates.

```text
# BEFORE
BANNED: **bold** *italic* `code` # headers. These break Telegram. ONLY use HTML tags.
```

```text
# AFTER
<output_format>
Replies go to Telegram as plain text. Stick to ordinary words, numbers,
and punctuation. Asterisks or underscores around words show up as literal
symbols, not formatting, so leave them out.
</output_format>
```

The AFTER version has a positive directive, an XML scope marker, and a one-sentence reason. The words "bold", "italic", "code", "headers" never appear in the prompt. The model has no banned-token list to parrot from.

### Example bot: few-shot diversity (TaskBot)

Symptom: a task-manager bot echoed "call supplier" into replies regardless of the actual task the user submitted. The phrase was leaking from the single few-shot example into every response.

Root cause: one example with one specific entity name. Mistral Small had no signal that "call supplier" was meant to vary - it treated the phrase as part of the structural template.

```text
# BEFORE - single example, invariant phrase
<example>add task: call supplier -> Task added: call supplier.</example>
```

```text
# AFTER - three examples, varied task types, varied phrasings
<examples>
Input: add task: send Q3 invoice by Friday
Output: Task added: send Q3 invoice by Friday.

Input: remind me to call the supplier tomorrow at 9am
Output: Reminder set: call the supplier, tomorrow at 9am.

Input: mark task 14 done
Output: Task 14 marked complete.
</examples>
```

Three distinct task types (create, remind, update). Three distinct phrasings. Every output is plain text, matching the positive directive above. The model can no longer treat any single entity name as a constant.

---

## References

- [Anthropic Prompt Engineering Guide - Be Clear and Direct](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) - canonical source for "Tell Claude what to do instead of what not to do"; the ellipses example; the rule that the model generalises from a one-sentence explanation.
- [Anthropic Prompt Engineering Guide - Multishot Prompting](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/multishot-prompting) - canonical source for 3-5 example recommendation; relevance, diversity, structure rules; `<examples>` and `<example>` tag convention.
- [Anastasiou et al., "Negation: A Pink Elephant in the LLMs' Room?"](https://arxiv.org/html/2503.22395v1) - March 2025 arxiv paper measuring negation degradation across Mistral Nemo 12B, Small 22B, Large 123B. The "scale narrows but does not close the gap" finding is the empirical basis for treating positive framing as a hard rule on Mistral Small.
- [Mistral Prompting Capabilities Guide](https://docs.mistral.ai/guides/prompting_capabilities) - official Mistral guidance recommending Markdown and XML-style tags for structure; alternating user/assistant role messages for few-shot examples; explicit constraints over blurry quantitative adjectives.
- [OpenAI Cookbook - Prompt Engineering](https://cookbook.openai.com/articles/related_resources) - general best practices reference; covers the same XML, few-shot, and positive-framing patterns from the OpenAI side, useful when porting prompts between providers.

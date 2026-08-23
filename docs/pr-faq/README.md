# turtleOS PR/FAQ

Working backwards: write the press release and the hard questions **before** the
feature is built. The customer is the practitioner (sometimes a hosted
practitioner; sometimes Spirit as the system that has to execute it — name which
one in the instance).

**Directory:** `docs/pr-faq/instances/` — one markdown file per feature.
**Check:** `tests/test_pr_faq_format.py` fails if an instance is missing a
required heading, and fails if a deliberately incomplete fixture is accepted.

## Required headings

Press release:

- **Headline**
- **Problem**
- **Solution**
- **Benefits**
- **Practitioner quote**
- **Getting started**

FAQ:

- **UX**
- **Not in scope**
- **Approach**
- **Risks**
- **Success / UX verification**

Heading titles must match these names exactly (as `##` or `###`). That is what
the check reads.

## Worked example

[Craft Turtle is Turtle](instances/craft-turtle-is-turtle.md) — retro-filled
from the 2026-08-18 identity fix, so the format is not an empty template.

## In progress (not an instance)

The attunement press release (craft eddy *main features of turtleos*, waiting
on Option B) was the first attempt to use this method on a live question.
Completing it is the practitioner's call and is not required for the format
to exist. Do not treat a citation as a finished instance.

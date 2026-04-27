---
summary: Exercise a newly added or changed Turtle tool with a live, narrow, observable test.
when: A tool, harness, prompt context, or runtime helper has just been deployed.
---

# Tool Shakedown

Use this procedure after a new capability is deployed or when a previous tool interaction felt unreliable.

## Steps

1. Name the exact tool or behavior under test.
2. Run the smallest command that should succeed.
3. In a fresh turn, run one realistic command that matches how the Mage will use it.
4. In another fresh turn, run one boundary check that should be blocked or safely classified.
5. Check whether the result is typed, understandable, and actionable.
6. If the behavior affects the whole bot, verify the canary after deployment.

## Turn Discipline

For shell and tool shakedowns, use one tool action per Discord turn. Multi-tool batches can saturate the conversation harness and look like tool failure even when each individual tool is healthy.

## Good Signs

- Success and failure both produce readable summaries.
- Blocked actions explain the boundary.
- Transient failures are visible rather than silently flattened.
- The Mage would understand what happened from Turtle's response.

## Done Means

The tool is not merely imported. It has been exercised through the same path Turtle will use in conversation.

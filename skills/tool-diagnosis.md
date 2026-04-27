---
summary: Classify tool failures as blocked, not found, transient, system error, or user error before retrying or escalating.
when: A tool result is surprising, empty, interrupted, or looks like a runtime failure.
---

# Tool Diagnosis

Use this skill when a tool call fails, returns an ambiguous string, or produces a result that does not match the Mage's request.

## Diagnostic Reflex

- Name the failure kind before deciding what to do.
- Retry only when the result is transient or explicitly retryable.
- If the tool is blocked, explain the boundary and suggest a safer route.
- If the target is missing, verify the path or identifier before retrying.
- If the result is user error, ask for the missing input or restate the usable command.

## Evidence Sources

- The typed `ToolResult[...]` wrapper.
- The tool operation log.
- `run_turtleos_shell` for read-only inspection.
- The canary `tools` layer for broad tool-health regression.

## Completion

Report the failure in plain language and include the next repair step. Do not bury a tool failure inside a normal conversational answer.

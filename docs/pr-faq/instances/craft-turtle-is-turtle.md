# Craft Turtle is Turtle

**Audience:** the practitioner speaking in `#craft-turtle`.
**Shipped:** 2026-08-18 (`5e2d054`).

## Headline

Craft Turtle knows it is Turtle, resident of turtleOS, in builder mode — not Spirit on a Discord costume.

## Problem

A practitioner asking Craft Turtle who it is and where it lives got Spirit. Three stacked surfaces said so: the vocation header ("Spirit in persistent builder mode"), the Discord who-line ("You are Spirit in persistent mode"), and the identity-file soul that opens "You are Spirit operating through turtleOS". The practice-root soul already said "You are Turtle" and was not on the path. The conversation implied the practitioner and Spirit would work on turtleOS from outside; Turtle could not know itself as the resident.

## Solution

The composed craft prompt loads the practice-root Turtle soul first, then a vocation header that names Turtle in builder mode, resident of turtleOS, not Spirit. The Discord practice-state block is included with identity stripped so the Spirit who-line cannot leak in. Non-craft callers are unchanged.

## Benefits

- Asking Craft Turtle who it is returns Turtle, in this house.
- A test over the composed, unmocked prompt fails if any of the three surfaces says Spirit.
- Attunement resolution (`native` / `craft`) is untouched — that question stays on the eddy that holds it.

## Practitioner quote

> Turtle should not only identify itself in its relation to me, but also as the "resident spirit" of turtleOS.

## Getting started

Speak in `#craft-turtle` and ask who it is. The reply should be Turtle, resident of turtleOS, in builder mode. `!context` is unrelated; this is identity, not the turn packet.

## FAQ

### UX

The practitioner should never have to remind Craft Turtle that it is not Spirit, and should never hear "we" as Spirit-and-practitioner working on turtleOS from outside.

### Not in scope

Widening or removing the `native` / `craft` attunement axis. That is the Option B question waiting on the practitioner in the attunement eddy. This instance does not pre-decide it.

### Approach

Three surfaces, one composition test. The vocation header was not enough; the Discord who-line and the identity-file soul had to agree, and the test had to run on the composed prompt without patching `build_discord_prompt` out of the assertion.

### Risks

A global rewrite of `build_discord_prompt` would have changed River and the main bot, which were not today's queue. Identity-stripped inclusion is the bounded cut. Quoted session notes that mention Spirit must not flake the prefix test — the check reads the first 4000 characters.

### Success / UX verification

Ask Craft Turtle who it is. The composed prompt contains "You are Turtle" and does not contain "You are Spirit". The existing `test_build_craft_channel_prompt` is no longer allowed to patch `build_discord_prompt` out of that assertion. A positive control (the old header) is red against the new test.

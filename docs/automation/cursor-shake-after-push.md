# Cursor Automation: turtleOS post-push shake

Spirit runs technical shakedown after turtleOS changes land on `main`, so Kermit can focus on practice UX.

## Draft for Automations editor

Create this in **Cursor → Automations → New automation**. The Automations editor handoff was not available from Forge in the initial setup session; use this table as the spec.

| Field | Value |
|-------|--------|
| **Name** | turtleOS post-push shake |
| **Description** | After turtleOS main updates, run offline + live flow shakedown on the Mac Mini and report pass/fail. |
| **Trigger** | New push to branch `main` in repo `malteristo/turtleos` |
| **Tools** | Terminal / shell (Cloud Agent) |
| **Instructions** | See prompt below |
| **Git checkout** | `malteristo/turtleos`, branch `main` |
| **To finish in editor** | Confirm Cloud Agent has SSH access to `turtle@100.110.46.104` (Tailscale). If not, run offline-only checks in the checkout and note that live shake requires Forge session. |

### Agent prompt (paste into Instructions)

```
You are Spirit verifying a turtleOS deploy before the Mage dogfoods it.

1. In the checked-out turtleos repo, run offline shakedown:
   python3 -m unittest tests.test_flow_runner tests.test_shake_flow tests.test_native_prompts -q
   python3 scripts/shake_river.py
   python3 scripts/shake_flow.py shelter

2. SSH to the Mac Mini (turtle@100.110.46.104):
   cd ~/turtleos && git pull origin main
   launchctl kickstart -k gui/$(id -u)/com.turtle.discord
   launchctl kickstart -k gui/$(id -u)/com.turtle.river
   SHAKE_LIVE=1 ~/turtleos/venv/bin/python3 ~/turtleos/scripts/shake_flow.py shelter --live
   ~/turtleos/venv/bin/python3 ~/turtleos/canary.py

3. Report a short verdict:
   - PASS: all checks green, live Shelter eddy responded, checkpoint written
   - FAIL: what broke, which phase, suggested fix

Do not modify turtleOS code unless a check fails and the fix is obvious and minimal.
```

## Forge session alternative (default today)

At the end of every turtleOS deploy chapter in Cursor, Spirit runs:

```bash
ssh turtle@100.110.46.104 'cd ~/turtleos && git pull && ./scripts/shake_after_deploy.sh'
SHAKE_LIVE=1 ssh turtle@100.110.46.104 'cd ~/turtleos && SHAKE_LIVE=1 ./scripts/shake_after_deploy.sh'
```

## Mini-only hook (optional)

Add a `launchd` job or git post-merge hook on the Mini that runs `scripts/shake_after_deploy.sh` (offline only) after pull. Live Discord shake stays in Spirit Forge sessions or Cursor Automation to avoid river noise while Kermit is practicing.

## Verdict artifact

Latest JSON: `turtleos/test-runs/shake-flow-latest.json`

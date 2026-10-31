#!/bin/bash
# post-receive hook for the house's workshop repository (~/repos/magic.git).
#
# When main is pushed, bring the house's checkout (~/workshop) up to it, so a session
# opened in the magic room stands on what was just released, not on what was there
# yesterday. Only a plain fast-forward, only while the checkout is on main. Anything
# else is left alone and said, and the push is never refused: this hook cannot fail a push.
#
# Bridging mechanism: once the house is main's only writer (`workshop.main_writable`),
# nothing arrives from outside and this does nothing. Remove it then.
# Install: cp scripts/workshop_post_receive.sh ~/repos/magic.git/hooks/post-receive
set -u
CHECKOUT="${WORKSHOP_CHECKOUT:-$HOME/workshop}"
REMOTE="${WORKSHOP_REMOTE:-turtle}"
unset GIT_DIR GIT_WORK_TREE GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES

while read -r _old _new ref; do
  [ "$ref" = "refs/heads/main" ] || continue
  if [ ! -d "$CHECKOUT/.git" ]; then
    echo "workshop: no checkout at $CHECKOUT; not updated"
    continue
  fi
  branch=$(git -C "$CHECKOUT" rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ "$branch" != "main" ]; then
    echo "workshop: checkout is on '$branch', not main; not updated"
    continue
  fi
  if git -C "$CHECKOUT" pull -q --ff-only "$REMOTE" main >/dev/null 2>&1; then
    echo "workshop: checkout now at $(git -C "$CHECKOUT" rev-parse --short HEAD)"
  else
    echo "workshop: checkout could not fast-forward (changes of its own?); not updated"
  fi
done
exit 0

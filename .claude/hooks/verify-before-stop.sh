#!/bin/bash
# Stop hook: invokes the verifier subagent before allowing task completion.
# Blocks if verification fails. Non-zero exit prevents Claude from ending the turn.

# Respect stop_hook_active to prevent infinite loops
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Only enforce on work that touched code
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null | head -20)
CODE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(ts|tsx|py|sql)$' | wc -l)

if [ "$CODE_CHANGES" -eq 0 ]; then
  # No code changed — nothing to verify, allow stop
  exit 0
fi

# Invoke verifier subagent
# (Claude Code will pick up this exit code; the subagent invocation
# is implicit via the Stop hook pattern documented in Anthropic's hooks guide)
echo "Verifier subagent should run before allowing task completion."
echo "Changed files: $CHANGED_FILES"

# If you want hard-enforced typecheck before stop:
if ! npm run typecheck 2>/dev/null; then
  echo "TypeScript errors present — blocking task completion."
  exit 2  # Exit code 2 tells Claude to not stop the turn
fi

exit 0

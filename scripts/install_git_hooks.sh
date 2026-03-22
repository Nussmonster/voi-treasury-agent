#!/bin/bash
# Run this once after git init to install a pre-commit hook
# that blocks accidental commit of secrets

mkdir -p ../.git/hooks
cat > ../.git/hooks/pre-commit << 'HOOK'
#!/bin/bash
# Block commits containing common secret patterns
if git diff --cached --name-only | grep -q "\.env$"; then
  echo "❌ BLOCKED: .env file detected in commit. Remove it first."
  echo "   Run: git reset HEAD .env"
  exit 1
fi
if git diff --cached | grep -qE "[a-z]{3,} [a-z]{3,} [a-z]{3,} [a-z]{3,} [a-z]{3,} [a-z]{3,}"; then
  echo "⚠️  WARNING: Possible mnemonic phrase detected in diff."
  echo "   Double-check you're not committing a wallet mnemonic."
  read -p "Continue anyway? (y/N): " confirm
  [[ "$confirm" != "y" ]] && exit 1
fi
exit 0
HOOK
chmod +x ../.git/hooks/pre-commit
echo "✅ Git pre-commit hook installed — .env files are now blocked from commits"

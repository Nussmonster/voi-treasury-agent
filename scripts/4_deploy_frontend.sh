#!/bin/bash
# ─────────────────────────────────────────────────────────────
# STEP 4: Deploy Frontend to GitHub Pages
# Prerequisites: git installed, GitHub account, .env file populated
# Usage: bash 4_deploy_frontend.sh <GITHUB_USERNAME> <REPO_NAME>
# Example: bash 4_deploy_frontend.sh alice voi-treasury-agent
# ─────────────────────────────────────────────────────────────

GITHUB_USER=${1:-"YOUR_GITHUB_USERNAME"}
REPO_NAME=${2:-"voi-treasury-agent"}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   GitHub Pages Deployment                ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Load .env
if [ -f ".env" ]; then
  export $(cat .env | xargs)
  echo "✅ Loaded config from .env"
  echo "   VTAG Asset ID : $VTAG_ASSET_ID"
  echo "   Vault App ID  : $VAULT_APP_ID"
  echo "   Vault Address : $VAULT_ADDRESS"
else
  echo "⚠️  No .env file found. Using placeholder values."
  VTAG_ASSET_ID="YOUR_ASSET_ID"
  VAULT_APP_ID="YOUR_APP_ID"
  VAULT_ADDRESS="YOUR_VAULT_ADDRESS"
fi

echo ""
echo "📁 Setting up GitHub Pages repo structure..."

# Create docs/ folder for GitHub Pages
mkdir -p docs

# Inject real values into the dashboard HTML
sed \
  -e "s/VTAG_ASSET_ID_PLACEHOLDER/$VTAG_ASSET_ID/g" \
  -e "s/VAULT_APP_ID_PLACEHOLDER/$VAULT_APP_ID/g" \
  -e "s/VAULT_ADDRESS_PLACEHOLDER/$VAULT_ADDRESS/g" \
  -e "s/GITHUB_USER_PLACEHOLDER/$GITHUB_USER/g" \
  ../frontend/index.html > docs/index.html

echo "✅ Dashboard injected with live contract values → docs/index.html"

# Disable Jekyll so GitHub Pages serves raw HTML directly
touch docs/.nojekyll
echo "✅ Added .nojekyll (disables Jekyll, serves raw HTML)"

# Initialize git if needed
if [ ! -d ".git" ]; then
  git init
  echo "✅ Git repo initialized"
fi

# Create .gitignore
cat > .gitignore << 'EOF'
node_modules/
__pycache__/
*.pyc
.env
*.log
EOF

# GitHub Actions workflow for auto-deploy on push
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml << 'EOF'
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Pages
        uses: actions/configure-pages@v4
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: './docs'
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
EOF

echo "✅ GitHub Actions workflow created"

# Stage everything
git add -A
git commit -m "🚀 Deploy VTAG Treasury Agent — Asset $VTAG_ASSET_ID, Vault $VAULT_APP_ID"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ READY TO PUSH!"
echo ""
echo "Run these commands to go live:"
echo ""
echo "  git remote add origin https://github.com/$GITHUB_USER/$REPO_NAME.git"
echo "  git branch -M main"
echo "  git push -u origin main"
echo ""
echo "Then in GitHub:"
echo "  Settings → Pages → Source: GitHub Actions"
echo ""
echo "🌐 Your live URL will be:"
echo "   https://$GITHUB_USER.github.io/$REPO_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

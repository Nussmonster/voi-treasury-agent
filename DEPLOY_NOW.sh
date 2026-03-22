#!/bin/bash
# ═══════════════════════════════════════════════════════════
# VTAG PERSONALISED DEPLOY SCRIPT
# Run this on your own machine after installing dependencies
# ═══════════════════════════════════════════════════════════
#
# PRE-REQUISITES (run once):
#   npm install algosdk
#   pip3 install algosdk pyteal
#
# STEP 1 — Fund these addresses from the Voi testnet faucet:
#   Owner  : CBRFUKPOKSBNRMD3PYPVAPZHA62XM6C2PDW5K5F3RYYYNT5ZTHALVEEQBY
#   Signer1: FNV77TOJZANJ55PORTE7LNIB7G3LUVFP5AHVTPCJLWZ2U5N6ZCQ3YZ7W5Q
#   Signer2: EQFNXH4CBFD4R7ZMWIHCOK76MYE5KTXYY35QHKHSHJOYYVL3UQSCQIOMS4
#   Signer3: 2EVWI3BNBUIEGQQA77XTYEXMNVBKC2LXWG7PLOHM2FNXHB54MZBN33NAD4
#
#   Faucet: Join discord.gg/voi-network → #bot-commands → /voi-testnet-faucet
#
# STEP 2 — Set your mnemonics as env vars (never pass as CLI args)
export VTAG_MNEMONIC_OWNER=""       # paste owner 25-word mnemonic here
export VTAG_MNEMONIC_SIGNER1=""     # paste signer1 mnemonic here

# STEP 3 — Deploy VTAG token
node scripts/2_deploy_token.js
# → note the ASSET_ID printed

# STEP 4 — Deploy multisig vault
python3 scripts/3_deploy_vault.py \
  --mnemonic "$VTAG_MNEMONIC_OWNER" \
  --asset-id REPLACE_WITH_ASSET_ID \
  --signer1 FNV77TOJZANJ55PORTE7LNIB7G3LUVFP5AHVTPCJLWZ2U5N6ZCQ3YZ7W5Q \
  --signer2 EQFNXH4CBFD4R7ZMWIHCOK76MYE5KTXYY35QHKHSHJOYYVL3UQSCQIOMS4 \
  --signer3 2EVWI3BNBUIEGQQA77XTYEXMNVBKC2LXWG7PLOHM2FNXHB54MZBN33NAD4 \
  --threshold 2
# → note the APP_ID and VAULT_ADDRESS printed

# STEP 5 — Deploy frontend to GitHub Pages
bash scripts/4_deploy_frontend.sh YOUR_GITHUB_USERNAME voi-treasury-agent

# STEP 6 — Install git safety hooks
bash scripts/install_git_hooks.sh

echo "🚀 VTAG Treasury Agent is live!"

#!/bin/bash
# ─────────────────────────────────────────────────────────────
# STEP 1: Create a Voi Testnet Wallet
# Run this script first. It installs algosdk and generates
# a fresh wallet address + mnemonic for the testnet.
# ─────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   VOI Treasury Agent — Wallet Setup      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
  echo "❌ Node.js not found. Install from https://nodejs.org (v18+)"
  exit 1
fi

# Install algosdk if needed
if [ ! -d "node_modules/algosdk" ]; then
  echo "📦 Installing algosdk..."
  npm install algosdk
fi

# Generate wallet
node -e "
const algosdk = require('algosdk');
const account = algosdk.generateAccount();
const mnemonic = algosdk.secretKeyToMnemonic(account.sk);

console.log('');
console.log('✅ Wallet generated successfully!');
console.log('');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('📬 Address:');
console.log('   ' + account.addr);
console.log('');
console.log('🔑 Mnemonic (25 words — SAVE THIS NOW):');
console.log('   ' + mnemonic);
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('');
console.log('NEXT STEPS:');
console.log('1. Copy and save your mnemonic OFFLINE — never share it');
console.log('2. Copy your address above');
console.log('3. Go to Voi Discord: https://discord.gg/voi-network');
console.log('   → In #bot-commands channel, type: /voi-testnet-faucet');
console.log('   → Paste your address to receive test VOI');
console.log('4. Check balance at: https://voi.observer/explorer/home');
console.log('5. Once funded, run: node 2_deploy_token.js "<YOUR_MNEMONIC>"');
console.log('');

// Save address to .env for next scripts
const fs = require('fs');
fs.writeFileSync('.env', 'WALLET_ADDRESS=' + account.addr + '\n');
console.log('✅ Address saved to .env file');
"

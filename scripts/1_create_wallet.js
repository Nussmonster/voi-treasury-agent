#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────
// STEP 1: Generate Voi Testnet Wallets
// Works on Windows, Mac, Linux — no bash needed
// Usage: node scripts/1_create_wallet.js
// ─────────────────────────────────────────────────────────────

const algosdk = require('algosdk');
const fs      = require('fs');
const path    = require('path');

const LABELS = [
  'Owner      (cold wallet — store offline)',
  'Signer 1   (AI agent hot key)',
  'Signer 2   (guardian key)',
  'Signer 3   (backup key)',
];

console.log('');
console.log('╔══════════════════════════════════════════════════╗');
console.log('║   VOI Treasury Agent — Wallet Generation        ║');
console.log('╚══════════════════════════════════════════════════╝');
console.log('');

const wallets = LABELS.map((label, i) => {
  const account  = algosdk.generateAccount();
  const mnemonic = algosdk.secretKeyToMnemonic(account.sk);
  return { label, address: account.addr.toString(), mnemonic };
});

wallets.forEach((w, i) => {
  console.log(`${'─'.repeat(54)}`);
  console.log(`🔑  Wallet ${i + 1}: ${w.label}`);
  console.log(`    Address : ${w.address}`);
  console.log(`    Mnemonic: ${w.mnemonic}`);
  console.log('');
});

console.log('─'.repeat(54));
console.log('');
console.log('⚠️  WRITE THE MNEMONICS ON PAPER NOW — never save to a file');
console.log('⚠️  Never share mnemonics with anyone');
console.log('');

// Save only public addresses to .env (no private keys)
const envPath = path.join(__dirname, '..', '.env');
let env = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';

// Remove any old address lines
env = env.split('\n').filter(l =>
  !l.startsWith('OWNER_ADDRESS') &&
  !l.startsWith('SIGNER_') &&
  !l.startsWith('WALLET_ADDRESS')
).join('\n').trim();

env += `\nOWNER_ADDRESS=${wallets[0].address}`;
env += `\nSIGNER_1=${wallets[1].address}`;
env += `\nSIGNER_2=${wallets[2].address}`;
env += `\nSIGNER_3=${wallets[3].address}\n`;

fs.writeFileSync(envPath, env.trim() + '\n');

console.log('✅ Public addresses saved to .env');
console.log('');
console.log('NEXT STEPS:');
console.log('1. Write down all 4 mnemonics on paper');
console.log('2. Fund each address at: discord.gg/voi-network → #bot-commands → /voi-testnet-faucet');
console.log('3. Then run: node scripts/2_deploy_token.js');
console.log('');

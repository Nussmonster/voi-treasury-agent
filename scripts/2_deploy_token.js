#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────
// STEP 2: Deploy VTAG Token (ASA) on Voi Testnet
// Usage: node 2_deploy_token.js "your 25 word mnemonic here"
// ─────────────────────────────────────────────────────────────

const algosdk = require('algosdk');

// Voi Testnet public API (no key needed)
const VOI_TESTNET_API  = 'https://testnet-api.voi.nodely.io';
const VOI_TESTNET_PORT = 443;
const VOI_API_TOKEN    = '';  // public node — no token required

const mnemonic = process.argv[2] || process.env.VTAG_MNEMONIC;
if (!mnemonic) {
  console.error('❌ Usage: node 2_deploy_token.js "word1...word25"');
  console.error('   Or set: export VTAG_MNEMONIC="word1...word25" (safer — not logged in history)');
  process.exit(1);
}

async function deployToken() {
  console.log('\n╔══════════════════════════════════════════╗');
  console.log('║   VTAG Token Deployment — Voi Testnet    ║');
  console.log('╚══════════════════════════════════════════╝\n');

  // Restore account from mnemonic
  const account = algosdk.mnemonicToSecretKey(mnemonic);
  console.log('🔑 Deploying from:', account.addr);

  // Connect to Voi testnet
  const client = new algosdk.Algodv2(VOI_API_TOKEN, VOI_TESTNET_API, VOI_TESTNET_PORT);

  // Check balance
  const info = await client.accountInformation(account.addr).do();
  const balanceVoi = info.amount / 1e6;
  console.log(`💰 Balance: ${balanceVoi.toFixed(2)} VOI`);

  if (balanceVoi < 1) {
    console.error('\n❌ Insufficient balance. Need at least 1 VOI.');
    console.error('   Get test VOI from Discord: /voi-testnet-faucet');
    process.exit(1);
  }

  // Get suggested params
  const params = await client.getTransactionParams().do();
  console.log(`📦 Network round: ${params.firstValid}`);

  // ── Create VTAG ASA ──────────────────────────────────────
  const totalSupply    = 10_000_000;   // 10M VTAG
  const decimals       = 6;
  const unitName       = 'VTAG';
  const assetName      = 'VOI Treasury Agent Token';
  const assetURL       = 'https://vtag.voi.network';    // your future site
  const managerAddr    = account.addr;
  const reserveAddr    = account.addr;
  const freezeAddr     = account.addr;
  const clawbackAddr   = account.addr;

  const txn = algosdk.makeAssetCreateTxnWithSuggestedParamsFromObject({
    from: account.addr,
    total: totalSupply * Math.pow(10, decimals),
    decimals,
    defaultFrozen: false,
    unitName,
    assetName,
    assetURL,
    manager: managerAddr,
    reserve: reserveAddr,
    freeze: freezeAddr,
    clawback: clawbackAddr,
    suggestedParams: params,
  });

  // Sign and send
  const signedTxn = txn.signTxn(account.sk);
  console.log('\n⏳ Submitting VTAG token creation transaction...');
  await client.sendRawTransaction(signedTxn).do();
  const txId = txn.txID().toString();
  console.log('📨 TX ID:', txId);

  // Wait for confirmation
  const result = await algosdk.waitForConfirmation(client, txId, 4);
  const assetId = result['asset-index'];

  console.log('\n✅ VTAG TOKEN DEPLOYED SUCCESSFULLY!');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🪙  Asset ID :', assetId);
  console.log('📛  Name     :', assetName);
  console.log('🔤  Symbol   :', unitName);
  console.log('🔢  Supply   :', totalSupply.toLocaleString(), unitName);
  console.log('🔍  Explorer : https://voi.observer/explorer/asset/' + assetId);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  // Save asset ID for next step
  const fs = require('fs');
  let env = fs.existsSync('.env') ? fs.readFileSync('.env', 'utf8') : '';
  env += `VTAG_ASSET_ID=${assetId}\n`;
  env += `DEPLOYER_ADDRESS=${account.addr}\n`;
  fs.writeFileSync('.env', env);
  console.log('\n✅ Asset ID saved to .env → run: node 3_deploy_vault.js next');
}

deployToken().catch(err => {
  console.error('\n❌ Deployment failed:', err.message);
  process.exit(1);
});

// ── SECURITY NOTE ────────────────────────────────────────────
// Passing mnemonic as a CLI argument stores it in shell history.
// Safer alternative: set env var instead:
//   export VTAG_MNEMONIC="word1 word2 ... word25"
//   node 2_deploy_token.js
// Then clear it after: unset VTAG_MNEMONIC
// ─────────────────────────────────────────────────────────────

#!/usr/bin/env node
/**
 * VTAG Multisig — Proposal Interaction Tool
 * ─────────────────────────────────────────
 * Usage:
 *   node multisig.js propose  --mnemonic "..." --amount 5000000 --dest <ADDR> --app <APP_ID>
 *   node multisig.js approve  --mnemonic "..." --id <PROP_ID>  --app <APP_ID>
 *   node multisig.js execute  --mnemonic "..." --id <PROP_ID>  --app <APP_ID>
 *   node multisig.js cancel   --mnemonic "..." --id <PROP_ID>  --app <APP_ID>
 *   node multisig.js status   --app <APP_ID>
 */

const algosdk = require('algosdk');
const crypto  = require('crypto');

const VOI_API = 'https://mainnet-api.voi.nodely.io';
const client  = new algosdk.Algodv2('', VOI_API, 443);

// ── Parse args ───────────────────────────────────────────────
const args   = process.argv.slice(2);
const action = args[0];
const flags  = {};
for (let i = 1; i < args.length; i += 2) {
  flags[args[i].replace('--', '')] = args[i + 1];
}

if (!action) {
  console.log('Usage: node multisig.js <propose|approve|execute|cancel|status> [--flags]');
  process.exit(1);
}

// ── Helper: load account from mnemonic or env ────────────────
function loadAccount() {
  const m = flags.mnemonic || process.env.VTAG_MNEMONIC;
  if (!m) { console.error('❌ --mnemonic required (or set VTAG_MNEMONIC env var)'); process.exit(1); }
  return algosdk.mnemonicToSecretKey(m);
}

// ── Helper: send and confirm ─────────────────────────────────
async function sendAndConfirm(signedTxn, label) {
  await client.sendRawTransaction(signedTxn).do();
  const txId = signedTxn.txID ? signedTxn.txID() : signedTxn.get_txid?.();
  console.log(`📨 TX ID: ${txId}`);
  await algosdk.waitForConfirmation(client, txId, 4);
  console.log(`✅ ${label} confirmed`);
  return txId;
}

// ── Helper: read global state ────────────────────────────────
async function getGlobalState(appId) {
  const app   = await client.getApplicationByID(parseInt(appId)).do();
  const state = {};
  (app.params['global-state'] || []).forEach(s => {
    const key = Buffer.from(s.key, 'base64').toString();
    const val = s.value.type === 1
      ? Buffer.from(s.value.bytes, 'base64')
      : s.value.uint;
    state[key] = val;
  });
  return state;
}

// ── status ───────────────────────────────────────────────────
async function status() {
  const appId = flags.app;
  if (!appId) { console.error('❌ --app required'); process.exit(1); }

  console.log(`\n📊 Vault Status — App ${appId}\n`);
  const s = await getGlobalState(appId);

  const addrOf = buf => buf && buf.length === 32
    ? algosdk.encodeAddress(new Uint8Array(buf))
    : '(not set)';

  console.log(`🏦 Vault Balance   : ${(await client.accountInformation(
    algosdk.getApplicationAddress(parseInt(appId))).do()).amount / 1e6} VOI`);
  console.log(`🔐 Threshold       : ${s['threshold']}-of-3`);
  console.log(`👑 Owner           : ${addrOf(s['owner'])}`);
  console.log(`🔑 Signer 1        : ${addrOf(s['signer_1'])}`);
  console.log(`🔑 Signer 2        : ${addrOf(s['signer_2'])}`);
  console.log(`🔑 Signer 3        : ${addrOf(s['signer_3'])}`);
  console.log(`💰 Total Deposits  : ${(s['total_deposits'] || 0) / 1e6} VOI`);
  console.log(`📈 Total Yield     : ${(s['total_yield'] || 0) / 1e6} VOI`);
  console.log(`🔄 Agent Cycles    : ${s['cycles'] || 0}`);

  const propAmt  = s['prop_amount'] || 0;
  const propId   = s['prop_id'] ? s['prop_id'].toString() : '';
  const propDest = addrOf(s['prop_dest']);
  const propAppr = s['prop_approvals'] || 0;
  const propRnd  = s['prop_round'] || 0;

  if (propAmt > 0) {
    const bits   = ['Signer1','Signer2','Signer3'].filter((_,i) => propAppr & (1 << i));
    console.log(`\n⏳ PENDING PROPOSAL`);
    console.log(`   ID         : ${propId}`);
    console.log(`   Amount     : ${propAmt / 1e6} VOI`);
    console.log(`   Destination: ${propDest}`);
    console.log(`   Approvals  : ${bits.join(', ')} (${bits.length}/${s['threshold']})`);
    console.log(`   Created    : Round ${propRnd}`);
  } else {
    console.log(`\n✅ No pending proposals`);
  }
}

// ── propose ──────────────────────────────────────────────────
async function propose() {
  const { amount, dest, app } = flags;
  if (!amount || !dest || !app) {
    console.error('❌ --amount --dest --app all required'); process.exit(1);
  }
  const acct    = loadAccount();
  const params  = await client.getTransactionParams().do();
  const propId  = crypto.randomBytes(8).toString('hex');   // unique proposal ID

  console.log(`\n📋 Creating proposal`);
  console.log(`   Amount : ${parseInt(amount) / 1e6} VOI`);
  console.log(`   To     : ${dest}`);
  console.log(`   ID     : ${propId}`);

  const txn = algosdk.makeApplicationNoOpTxnFromObject({
    from:            acct.addr,
    appIndex:        parseInt(app),
    appArgs:         [
      new TextEncoder().encode('propose'),
      algosdk.encodeUint64(parseInt(amount)),
      new TextEncoder().encode(propId),
    ],
    accounts:        [dest],
    suggestedParams: params,
  });

  await sendAndConfirm(txn.signTxn(acct.sk), 'Proposal submitted');
  console.log(`\n💾 Save this proposal ID: ${propId}`);
  console.log(`   Share it with other signers to approve.`);
}

// ── approve ──────────────────────────────────────────────────
async function approve() {
  const { id, app } = flags;
  if (!id || !app) { console.error('❌ --id --app required'); process.exit(1); }
  const acct   = loadAccount();
  const params = await client.getTransactionParams().do();

  console.log(`\n✍️  Approving proposal ${id}`);

  const txn = algosdk.makeApplicationNoOpTxnFromObject({
    from:            acct.addr,
    appIndex:        parseInt(app),
    appArgs:         [
      new TextEncoder().encode('approve'),
      new TextEncoder().encode(id),
    ],
    suggestedParams: params,
  });

  await sendAndConfirm(txn.signTxn(acct.sk), 'Approval recorded on-chain');
}

// ── execute ──────────────────────────────────────────────────
async function execute() {
  const { id, app } = flags;
  if (!id || !app) { console.error('❌ --id --app required'); process.exit(1); }
  const acct   = loadAccount();
  const params = await client.getTransactionParams().do();

  // Check proposal state first
  const s        = await getGlobalState(app);
  const propId   = s['prop_id'] ? s['prop_id'].toString() : '';
  if (propId !== id) {
    console.error(`❌ Proposal ${id} not found on-chain (current: ${propId})`);
    process.exit(1);
  }
  const propAppr = s['prop_approvals'] || 0;
  const threshold = s['threshold'];
  const bits     = [1,2,4].filter(b => propAppr & b).length;
  if (bits < threshold) {
    console.error(`❌ Not enough approvals: ${bits}/${threshold}`);
    process.exit(1);
  }

  console.log(`\n🚀 Executing proposal ${id} (${bits}/${threshold} approvals)`);

  const txn = algosdk.makeApplicationNoOpTxnFromObject({
    from:            acct.addr,
    appIndex:        parseInt(app),
    appArgs:         [
      new TextEncoder().encode('execute'),
      new TextEncoder().encode(id),
    ],
    accounts:        [algosdk.encodeAddress(new Uint8Array(s['prop_dest']))],
    suggestedParams: params,
  });

  await sendAndConfirm(txn.signTxn(acct.sk), 'Proposal executed — funds transferred');
}

// ── cancel ───────────────────────────────────────────────────
async function cancel() {
  const { id, app } = flags;
  if (!id || !app) { console.error('❌ --id --app required'); process.exit(1); }
  const acct   = loadAccount();
  const params = await client.getTransactionParams().do();

  console.log(`\n🗑️  Cancelling proposal ${id}`);

  const txn = algosdk.makeApplicationNoOpTxnFromObject({
    from:            acct.addr,
    appIndex:        parseInt(app),
    appArgs:         [
      new TextEncoder().encode('cancel'),
      new TextEncoder().encode(id),
    ],
    suggestedParams: params,
  });

  await sendAndConfirm(txn.signTxn(acct.sk), 'Proposal cancelled');
}

// ── Dispatch ─────────────────────────────────────────────────
const dispatch = { propose, approve, execute, cancel, status };
if (!dispatch[action]) {
  console.error(`❌ Unknown action: ${action}`);
  console.error(`   Valid: propose | approve | execute | cancel | status`);
  process.exit(1);
}

dispatch[action]().catch(err => {
  console.error('\n❌ Error:', err.message);
  process.exit(1);
});

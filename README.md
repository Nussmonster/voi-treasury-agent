# VOI Treasury Agent — Full Stack Deployment Guide

> Autonomous AI treasury agent on the Voi Network blockchain.
> VTAG token + smart contract vault + AI-powered dashboard.

---

## What You're Deploying

| Component | Technology | Status |
|---|---|---|
| **VTAG Token** | ARC-0003 ASA on Voi | Script ready |
| **Treasury Vault** | PyTeal AVM v8 smart contract | Script ready |
| **AI Agent** | Claude API (claude-sonnet-4) | Live |
| **Frontend** | HTML/JS + algosdk | GitHub Pages |

---

## Prerequisites

Install these first:

```bash
# Node.js v18+ (for algosdk)
https://nodejs.org

# Python 3.9+ (for PyTeal vault deployment)
https://python.org

# Git
https://git-scm.com
```

---

## Step 1 — Generate Your Wallet

```bash
cd scripts
npm install algosdk
bash 1_create_wallet.sh
```

✅ This outputs:
- Your **Voi testnet address**
- Your **25-word mnemonic** (save this offline!)

---

## Step 2 — Fund Your Wallet (Testnet Faucet)

1. Join Voi Discord: **https://discord.gg/voi-network**
2. Go to `#bot-commands` channel
3. Type: `/voi-testnet-faucet`
4. Paste your address
5. Wait ~30 seconds for funds
6. Verify at: **https://voi.observer/explorer/home**

You need at least **2 VOI** to deploy.

---

## Step 3 — Deploy VTAG Token

```bash
node 2_deploy_token.js "word1 word2 word3 ... word25"
```

✅ This creates a 10,000,000 VTAG ASA on Voi testnet.

Outputs:
```
✅ VTAG TOKEN DEPLOYED SUCCESSFULLY!
🪙  Asset ID : 12345678
🔍  Explorer : https://voi.observer/explorer/asset/12345678
```

---

## Step 4 — Deploy Multisig Treasury Vault

First, generate 3 separate signer wallets (repeat `1_create_wallet.sh` 3 times):

```bash
# Signer 1 — AI agent hot key (lives on your server)
bash 1_create_wallet.sh   # save address as SIGNER_1

# Signer 2 — Guardian key (your personal hardware wallet or Kibisis)
bash 1_create_wallet.sh   # save address as SIGNER_2

# Signer 3 — Backup key (cold storage, locked away)
bash 1_create_wallet.sh   # save address as SIGNER_3
```

Then deploy with 2-of-3 threshold:

```bash
pip3 install algosdk pyteal
python3 3_deploy_vault.py \
  --mnemonic "your 25 words" \
  --asset-id 12345678 \
  --signer1 <SIGNER_1_ADDRESS> \
  --signer2 <SIGNER_2_ADDRESS> \
  --signer3 <SIGNER_3_ADDRESS> \
  --threshold 2
```

✅ Deploys a 2-of-3 multisig vault where:
- Withdrawals < 1 VOI: any single signer executes immediately (agent routine ops)
- Withdrawals >= 1 VOI: requires proposal → 2 approvals → 5-round timelock → execute
- Owner key rotates signers — keep it in cold storage

## Step 4b — Using the Multisig CLI

```bash
# Check vault status and any pending proposals
node multisig.js status --app <APP_ID>

# Signer 1 proposes a large withdrawal
node multisig.js propose --mnemonic "signer1 words" \
  --amount 5000000 --dest <POOL_ADDRESS> --app <APP_ID>
# → outputs a PROPOSAL_ID (e.g. a3f9b2c1...)

# Signer 2 approves it
node multisig.js approve --mnemonic "signer2 words" \
  --id a3f9b2c1 --app <APP_ID>

# Anyone executes after timelock (~15 seconds)
node multisig.js execute --mnemonic "signer1 words" \
  --id a3f9b2c1 --app <APP_ID>

# Cancel a proposal (owner or 2+ signers)
node multisig.js cancel --mnemonic "owner words" \
  --id a3f9b2c1 --app <APP_ID>
```

---

## Step 5 — Deploy Frontend to GitHub Pages

```bash
bash 4_deploy_frontend.sh YOUR_GITHUB_USERNAME voi-treasury-agent
```

Then push to GitHub:
```bash
git remote add origin https://github.com/YOUR_USERNAME/voi-treasury-agent.git
git branch -M main
git push -u origin main
```

Then in GitHub:
`Settings → Pages → Source: GitHub Actions`

✅ **Your live URL:** `https://YOUR_USERNAME.github.io/voi-treasury-agent`

---

## Interacting with the Vault

Once deployed, the frontend connects live to your vault via the Voi testnet API.

### Deposit VOI
Click **"+ Deposit VOI"** in the dashboard.

### Run Agent Cycle
Click **"↻ Cycle"** — the agent checks pool ratios, records yield, and logs on-chain.

### Chat with the Agent
The AI agent (powered by Claude) can answer:
- *"rebalance pools"*
- *"what's the risk score"*
- *"show yield breakdown"*
- *"how much VOI is in the vault"*

---

## Contract Architecture

```
Treasury Vault (AVM App)
├── Global State
│   ├── owner        → deployer address
│   ├── agent        → authorized rebalancer
│   ├── total_deposits → cumulative VOI in
│   ├── total_yield  → cumulative yield recorded
│   ├── cycles       → number of agent runs
│   └── vtag_id      → VTAG ASA asset ID
│
├── Methods
│   ├── deposit      → accept VOI payment
│   ├── withdraw     → agent-authorized withdrawal
│   ├── record_yield → log yield per cycle
│   ├── set_agent    → rotate agent address
│   └── optin_vtag   → opt vault into VTAG token
```

---

## Upgrade Path (Mainnet)

When ready for mainnet:

1. Change `VOI_TESTNET_API` → `https://mainnet-api.voi.nodly.io`
2. Re-run deploy scripts with funded mainnet wallet
3. Integrate [UseWallet](https://github.com/txnlab/use-wallet) for real wallet signing
4. Add Nomadex API for live pool data
5. Issue real VTAG with DAO governance

---

## Resources

| Resource | URL |
|---|---|
| Voi Explorer | https://voi.observer/explorer/home |
| Voi Docs | https://docs.voi.network |
| Voi Discord | https://discord.gg/voi-network |
| algosdk docs | https://algorand.github.io/js-algorand-sdk |
| PyTeal docs | https://pyteal.readthedocs.io |
| Nomadex DEX | https://nomadex.app |

---

*Built with algosdk, PyTeal, Claude API, and deployed on Voi Network.*

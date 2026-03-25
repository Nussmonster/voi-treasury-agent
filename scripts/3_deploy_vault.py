#!/usr/bin/env python3
"""
STEP 3: Deploy Treasury Vault — Multisig Edition
Usage: python3 3_deploy_vault.py --mnemonic "25 words" --asset-id <ID> \
       --signer1 <ADDR> --signer2 <ADDR> --signer3 <ADDR> [--threshold 2]

Multisig architecture:
  - 3 signer slots stored on-chain (signer_1, signer_2, signer_3)
  - Configurable threshold (default 2-of-3)
  - Small ops  (< 1 VOI): any single signer executes immediately
  - Large ops  (>= 1 VOI): propose → M-of-N approve → timelock → execute
  - Timelock: 5 rounds minimum before execution (~15s on Voi)
  - Owner (cold wallet) rotates signers — cannot be a signer
  - Contract is immutable (no update/delete)
"""

import sys
import base64
import argparse
from pathlib import Path

try:
    from algosdk import account, mnemonic, transaction, encoding
    from algosdk.v2client import algod
    from pyteal import *
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "py-algorand-sdk", "pyteal"])
    from algosdk import account, mnemonic, transaction, encoding
    from algosdk.v2client import algod
    from pyteal import *

# ── Voi Testnet config ───────────────────────────────────────
VOI_API   = "https://mainnet-api.voi.nodely.io"
VOI_TOKEN = ""
VOI_PORT  = 443

# ── Global state schema ──────────────────────────────────────
# Uints  (8): threshold, total_deposits, total_yield, cycles,
#             vtag_id, prop_amount, prop_round, prop_approvals
# Bytes  (6): owner, signer_1, signer_2, signer_3, prop_dest, prop_id
NUM_UINTS       = 8
NUM_BYTE_SLICES = 6


def treasury_vault_multisig(vtag_asset_id: int):

    # ── State keys ───────────────────────────────────────────
    OWNER_KEY      = Bytes("owner")
    SIGNER_1       = Bytes("signer_1")
    SIGNER_2       = Bytes("signer_2")
    SIGNER_3       = Bytes("signer_3")
    THRESHOLD_KEY  = Bytes("threshold")
    TOTAL_DEPOSITS = Bytes("total_deposits")
    TOTAL_YIELD    = Bytes("total_yield")
    CYCLE_COUNT    = Bytes("cycles")
    VTAG_ID_KEY    = Bytes("vtag_id")
    PROP_AMOUNT    = Bytes("prop_amount")
    PROP_DEST      = Bytes("prop_dest")
    PROP_APPROVALS = Bytes("prop_approvals")
    PROP_ROUND     = Bytes("prop_round")
    PROP_ID        = Bytes("prop_id")

    # ── Constants ────────────────────────────────────────────
    AUTO_LIMIT     = Int(1_000_000)    # 1 VOI in microVOI — below this = no proposal needed
    MIN_ROUNDS     = Int(5)            # timelock: ~15 seconds on Voi (3s/round)

    # ── Helpers ──────────────────────────────────────────────
    sender       = Txn.sender()
    is_owner     = sender == App.globalGet(OWNER_KEY)
    is_signer_1  = sender == App.globalGet(SIGNER_1)
    is_signer_2  = sender == App.globalGet(SIGNER_2)
    is_signer_3  = sender == App.globalGet(SIGNER_3)
    is_any_signer = Or(is_signer_1, is_signer_2, is_signer_3)

    vault_balance  = Balance(Global.current_application_address())
    threshold      = App.globalGet(THRESHOLD_KEY)
    current_round  = Global.round()

    # Signer index (1, 2, 3 — 0 = not a signer)
    signer_index = Cond(
        [is_signer_1, Int(1)],
        [is_signer_2, Int(2)],
        [is_signer_3, Int(3)],
        [Int(1),      Int(0)],
    )
    # Bitmask bit: index 1 → bit 0, index 2 → bit 1, index 3 → bit 2
    signer_bit = ShiftLeft(Int(1), signer_index - Int(1))

    # Count approvals from the bitmask (3-bit popcount)
    approvals       = App.globalGet(PROP_APPROVALS)
    approval_count  = (
        (approvals & Int(1)) +
        ((approvals >> Int(1)) & Int(1)) +
        ((approvals >> Int(2)) & Int(1))
    )

    # ── On creation ─────────────────────────────────────────
    init_threshold = Btoi(Txn.application_args[0])
    init_signer1   = Txn.accounts[1]
    init_signer2   = Txn.accounts[2]
    init_signer3   = Txn.accounts[3]

    on_create = Seq([
        Assert(init_threshold >= Int(1)),
        Assert(init_threshold <= Int(3)),
        Assert(sender != init_signer1),        # owner must be cold — not a hot signer
        Assert(sender != init_signer2),
        Assert(sender != init_signer3),
        Assert(init_signer1 != init_signer2),  # signers must be distinct
        Assert(init_signer1 != init_signer3),
        Assert(init_signer2 != init_signer3),
        App.globalPut(OWNER_KEY,      sender),
        App.globalPut(THRESHOLD_KEY,  init_threshold),
        App.globalPut(SIGNER_1,       init_signer1),
        App.globalPut(SIGNER_2,       init_signer2),
        App.globalPut(SIGNER_3,       init_signer3),
        App.globalPut(TOTAL_DEPOSITS, Int(0)),
        App.globalPut(TOTAL_YIELD,    Int(0)),
        App.globalPut(VTAG_ID_KEY,    Int(vtag_asset_id)),
        App.globalPut(CYCLE_COUNT,    Int(0)),
        App.globalPut(PROP_AMOUNT,    Int(0)),
        App.globalPut(PROP_APPROVALS, Int(0)),
        App.globalPut(PROP_ROUND,     Int(0)),
        App.globalPut(PROP_DEST,      Bytes("")),
        App.globalPut(PROP_ID,        Bytes("")),
        Approve(),
    ])

    # ── Deposit VOI ─────────────────────────────────────────
    deposit_amount = Gtxn[0].amount()
    on_deposit = Seq([
        Assert(Global.group_size() == Int(2)),
        Assert(Txn.group_index() == Int(1)),
        Assert(Gtxn[0].type_enum() == TxnType.Payment),
        Assert(Gtxn[0].receiver() == Global.current_application_address()),
        Assert(Gtxn[0].close_remainder_to() == Global.zero_address()),
        App.globalPut(TOTAL_DEPOSITS,
            App.globalGet(TOTAL_DEPOSITS) + deposit_amount),
        Approve(),
    ])

    # ── Small withdraw: single signer, below AUTO_LIMIT ─────
    small_amount = Btoi(Txn.application_args[1])
    small_dest   = Txn.accounts[1]
    max_small    = vault_balance / Int(20)  # 5% cap for single-signer ops

    on_withdraw_small = Seq([
        Assert(is_any_signer),
        Assert(small_amount > Int(0)),
        Assert(small_amount < AUTO_LIMIT),
        Assert(small_amount <= max_small),
        Assert(vault_balance >= small_amount + Int(500_000)),
        InnerTxnBuilder.Execute({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver:  small_dest,
            TxnField.amount:    small_amount,
            TxnField.fee:       Int(1_000),
        }),
        Approve(),
    ])

    # ── Propose large withdrawal ─────────────────────────────
    prop_amount_arg = Btoi(Txn.application_args[1])
    prop_dest_arg   = Txn.accounts[1]
    prop_id_arg     = Txn.application_args[2]

    on_propose = Seq([
        Assert(is_any_signer),
        Assert(prop_amount_arg >= AUTO_LIMIT),
        Assert(prop_amount_arg <= vault_balance / Int(10)),   # 10% cap
        Assert(vault_balance >= prop_amount_arg + Int(500_000)),
        Assert(App.globalGet(PROP_AMOUNT) == Int(0)),         # no open proposal
        App.globalPut(PROP_AMOUNT,    prop_amount_arg),
        App.globalPut(PROP_DEST,      prop_dest_arg),
        App.globalPut(PROP_ID,        prop_id_arg),
        App.globalPut(PROP_ROUND,     current_round),
        App.globalPut(PROP_APPROVALS, signer_bit),            # proposer auto-approves
        Approve(),
    ])

    # ── Approve a pending proposal ───────────────────────────
    approve_id       = Txn.application_args[1]
    already_approved = (App.globalGet(PROP_APPROVALS) & signer_bit) != Int(0)

    on_approve = Seq([
        Assert(is_any_signer),
        Assert(App.globalGet(PROP_AMOUNT) > Int(0)),
        Assert(App.globalGet(PROP_ID) == approve_id),
        Assert(Not(already_approved)),                        # no double-vote
        App.globalPut(PROP_APPROVALS,
            App.globalGet(PROP_APPROVALS) | signer_bit),
        Approve(),
    ])

    # ── Execute an approved proposal (after timelock) ────────
    execute_id     = Txn.application_args[1]
    rounds_elapsed = current_round - App.globalGet(PROP_ROUND)

    on_execute = Seq([
        Assert(is_any_signer),
        Assert(App.globalGet(PROP_AMOUNT) > Int(0)),
        Assert(App.globalGet(PROP_ID) == execute_id),
        Assert(approval_count >= threshold),                  # M-of-N met
        Assert(rounds_elapsed >= MIN_ROUNDS),                 # timelock passed
        Assert(vault_balance >= App.globalGet(PROP_AMOUNT) + Int(500_000)),
        InnerTxnBuilder.Execute({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver:  App.globalGet(PROP_DEST),
            TxnField.amount:    App.globalGet(PROP_AMOUNT),
            TxnField.fee:       Int(1_000),
        }),
        App.globalPut(PROP_AMOUNT,    Int(0)),
        App.globalPut(PROP_APPROVALS, Int(0)),
        App.globalPut(PROP_ROUND,     Int(0)),
        App.globalPut(PROP_DEST,      Bytes("")),
        App.globalPut(PROP_ID,        Bytes("")),
        Approve(),
    ])

    # ── Cancel a proposal ────────────────────────────────────
    cancel_id = Txn.application_args[1]
    on_cancel = Seq([
        Assert(Or(is_owner, approval_count >= threshold)),
        Assert(App.globalGet(PROP_ID) == cancel_id),
        App.globalPut(PROP_AMOUNT,    Int(0)),
        App.globalPut(PROP_APPROVALS, Int(0)),
        App.globalPut(PROP_ROUND,     Int(0)),
        App.globalPut(PROP_DEST,      Bytes("")),
        App.globalPut(PROP_ID,        Bytes("")),
        Approve(),
    ])

    # ── Record yield / cycle ─────────────────────────────────
    yield_amount = Btoi(Txn.application_args[1])
    on_record_yield = Seq([
        Assert(is_any_signer),
        App.globalPut(TOTAL_YIELD,
            App.globalGet(TOTAL_YIELD) + yield_amount),
        App.globalPut(CYCLE_COUNT,
            App.globalGet(CYCLE_COUNT) + Int(1)),
        Approve(),
    ])

    # ── Rotate a signer (owner only) ─────────────────────────
    signer_slot = Btoi(Txn.application_args[1])
    new_signer  = Txn.accounts[1]

    on_rotate_signer = Seq([
        Assert(is_owner),
        Assert(new_signer != App.globalGet(OWNER_KEY)),
        Assert(signer_slot >= Int(1)),
        Assert(signer_slot <= Int(3)),
        If(signer_slot == Int(1)).Then(Seq([
            Assert(new_signer != App.globalGet(SIGNER_2)),
            Assert(new_signer != App.globalGet(SIGNER_3)),
            App.globalPut(SIGNER_1, new_signer),
        ])).ElseIf(signer_slot == Int(2)).Then(Seq([
            Assert(new_signer != App.globalGet(SIGNER_1)),
            Assert(new_signer != App.globalGet(SIGNER_3)),
            App.globalPut(SIGNER_2, new_signer),
        ])).Else(Seq([
            Assert(new_signer != App.globalGet(SIGNER_1)),
            Assert(new_signer != App.globalGet(SIGNER_2)),
            App.globalPut(SIGNER_3, new_signer),
        ])),
        Approve(),
    ])

    # ── Opt-in to VTAG ASA (owner only) ─────────────────────
    on_optin_vtag = Seq([
        Assert(is_owner),
        InnerTxnBuilder.Execute({
            TxnField.type_enum:      TxnType.AssetTransfer,
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.xfer_asset:     App.globalGet(VTAG_ID_KEY),
            TxnField.asset_amount:   Int(0),
            TxnField.fee:            Int(1_000),
        }),
        Approve(),
    ])

    # ── Router ───────────────────────────────────────────────
    action  = Txn.application_args[0]
    on_call = Cond(
        [action == Bytes("deposit"),        on_deposit],
        [action == Bytes("withdraw_small"), on_withdraw_small],
        [action == Bytes("propose"),        on_propose],
        [action == Bytes("approve"),        on_approve],
        [action == Bytes("execute"),        on_execute],
        [action == Bytes("cancel"),         on_cancel],
        [action == Bytes("record_yield"),   on_record_yield],
        [action == Bytes("rotate_signer"),  on_rotate_signer],
        [action == Bytes("optin_vtag"),     on_optin_vtag],
    )

    program = Cond(
        [Txn.application_id() == Int(0),                        on_create],
        [Txn.on_completion() == OnCompletion.DeleteApplication, Reject()],
        [Txn.on_completion() == OnCompletion.UpdateApplication, Reject()],
        [Txn.on_completion() == OnCompletion.OptIn,             Approve()],
        [Txn.on_completion() == OnCompletion.CloseOut,          Approve()],
        [Txn.on_completion() == OnCompletion.NoOp,              on_call],
    )

    return program


def clear_state_program():
    return Approve()


def compile_contract(client, program):
    teal   = compileTeal(program, mode=Mode.Application, version=8)
    result = client.compile(teal)
    return base64.b64decode(result["result"])


def deploy_vault(deployer_mnemonic: str, vtag_asset_id: int,
                 signer1: str, signer2: str, signer3: str, threshold: int):

    print("\n╔══════════════════════════════════════════════════╗")
    print("║   Treasury Vault (Multisig) — Voi Testnet       ║")
    print("╚══════════════════════════════════════════════════╝\n")
    print(f"🔐 Multisig config : {threshold}-of-3")
    print(f"   Signer 1 (Agent)   : {signer1}")
    print(f"   Signer 2 (Guardian): {signer2}")
    print(f"   Signer 3 (Backup)  : {signer3}\n")

    private_key   = mnemonic.to_private_key(deployer_mnemonic)
    deployer_addr = account.address_from_private_key(private_key)
    print(f"🔑 Owner (cold wallet): {deployer_addr}")
    print(f"⚠️  Move this key to cold storage after deployment.\n")

    # Validate addresses
    for label, addr in [("Signer 1", signer1), ("Signer 2", signer2), ("Signer 3", signer3)]:
        try:
            encoding.decode_address(addr)
        except Exception:
            print(f"❌ Invalid address for {label}: {addr}"); sys.exit(1)
        if addr == deployer_addr:
            print(f"❌ {label} cannot equal the owner address"); sys.exit(1)

    if len({signer1, signer2, signer3}) != 3:
        print("❌ All three signer addresses must be distinct"); sys.exit(1)

    client  = algod.AlgodClient(VOI_TOKEN, VOI_API,
                                 headers={"User-Agent": "vtag-multisig/1.0"})
    info    = client.account_info(deployer_addr)
    balance = info["amount"] / 1e6
    print(f"💰 Balance : {balance:.2f} VOI")
    if balance < 3:
        print("❌ Need at least 3 VOI (multisig contract is larger)"); sys.exit(1)

    print("⚙️  Compiling multisig vault contract...")
    approval_prog = compile_contract(client, treasury_vault_multisig(vtag_asset_id))
    clear_prog    = compile_contract(client, clear_state_program())
    print("✅ Compilation successful\n")

    params = client.suggested_params()
    txn    = transaction.ApplicationCreateTxn(
        sender           = deployer_addr,
        sp               = params,
        on_complete      = transaction.OnComplete.NoOpOC,
        approval_program = approval_prog,
        clear_program    = clear_prog,
        global_schema    = transaction.StateSchema(
                               num_uints       = NUM_UINTS,
                               num_byte_slices = NUM_BYTE_SLICES),
        local_schema     = transaction.StateSchema(num_uints=0, num_byte_slices=0),
        extra_pages      = 1,
        app_args         = [threshold.to_bytes(8, "big")],
        accounts         = [signer1, signer2, signer3],
    )

    signed_txn = txn.sign(private_key)
    print("⏳ Submitting vault deployment transaction...")
    tx_id = client.send_transaction(signed_txn)
    print(f"📨 TX ID: {tx_id}")

    result        = transaction.wait_for_confirmation(client, tx_id, 4)
    app_id        = result["application-index"]
    import algosdk
    vault_address = algosdk.logic.get_application_address(app_id)

    print("\n⏳ Funding vault (0.6 VOI minimum balance)...")
    fund_txn = transaction.PaymentTxn(
        sender=deployer_addr, sp=params,
        receiver=vault_address, amt=600_000,
    )
    client.send_transaction(fund_txn.sign(private_key))
    transaction.wait_for_confirmation(client, fund_txn.get_txid(), 4)
    print("✅ Vault funded")

    print("\n✅ MULTISIG VAULT DEPLOYED!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🏦  App ID        : {app_id}")
    print(f"📬  Vault Address : {vault_address}")
    print(f"🔐  Threshold     : {threshold}-of-3")
    print(f"🪙  VTAG Asset ID : {vtag_asset_id}")
    print(f"🔍  Explorer      : https://voi.observer/explorer/application/{app_id}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("⚠️  SECURITY CHECKLIST:")
    print("   [ ] Move owner mnemonic to cold storage / hardware wallet")
    print("   [ ] Distribute signer keys to separate people/machines")
    print("   [ ] Run: bash scripts/install_git_hooks.sh")
    print("   [ ] Test deposit + small withdraw before going live")
    print("   [ ] Test propose → approve (2nd signer) → execute flow")
    print()

    env_path = Path(".env")
    env      = env_path.read_text() if env_path.exists() else ""
    env     += f"VAULT_APP_ID={app_id}\n"
    env     += f"VAULT_ADDRESS={vault_address}\n"
    env     += f"MULTISIG_THRESHOLD={threshold}\n"
    env     += f"SIGNER_1={signer1}\n"
    env     += f"SIGNER_2={signer2}\n"
    env     += f"SIGNER_3={signer3}\n"
    env_path.write_text(env)
    print("✅ Config saved to .env → run: bash 4_deploy_frontend.sh")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy VTAG Multisig Treasury Vault")
    parser.add_argument("--mnemonic",  required=True, help="Owner 25-word mnemonic (cold wallet)")
    parser.add_argument("--asset-id",  required=True, type=int)
    parser.add_argument("--signer1",   required=True, help="Hot signer 1 (AI agent key)")
    parser.add_argument("--signer2",   required=True, help="Hot signer 2 (guardian)")
    parser.add_argument("--signer3",   required=True, help="Hot signer 3 (backup)")
    parser.add_argument("--threshold", default=2,     type=int, help="Required approvals (default: 2)")
    args = parser.parse_args()
    deploy_vault(args.mnemonic, args.asset_id,
                 args.signer1, args.signer2, args.signer3, args.threshold)

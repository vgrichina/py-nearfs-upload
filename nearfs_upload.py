import asyncio
import aiohttp
import os
from typing import List, Dict, Any
from py_near.account import Account
from py_near.transactions import create_function_call_action
from ipfs_helpers import (
    compute_hash, cid_to_string, pack_cid, write_pb_node, read_cid
)

DEFAULT_OPTIONS = {
    "log": print,
    "status_callback": lambda current_blocks, total_blocks: None,
    "timeout": 2.5,
    "retry_count": 3,
    "gateway_url": "https://ipfs.web4.near.page",
    "account_id": None,
    "private_key": None,
    "network_id": "mainnet",
}
async def is_already_uploaded(cid: bytes, account: Account, options: Dict[str, Any] = DEFAULT_OPTIONS) -> bool:
    log, timeout, retry_count, gateway_url = options["log"], options["timeout"], options["retry_count"], options["gateway_url"]
    cid32 = cid_to_string(cid)
    url_to_check = f"{gateway_url}/ipfs/{cid32}"

    for _ in range(retry_count):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url_to_check, timeout=timeout) as response:
                    if response.status == 200:
                        log(f"Block {cid32} already exists on chain, skipping")
                        return True
                    if response.status != 404:
                        raise Exception(f"Unexpected status code {response.status} for {url_to_check}")
        except asyncio.TimeoutError:
            log(f"Timeout while checking {url_to_check}")
            continue
        except Exception as e:
            log(f"Error checking block {cid32}: {str(e)}")
            await asyncio.sleep(1)
    
    return False

def split_on_batches(new_blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    current_batch = []
    batches = [current_batch]
    MAX_BATCH_ACTIONS = 7
    MAX_BATCH_BYTES = 256 * 1024
    
    for block in new_blocks:
        if len(current_batch) >= MAX_BATCH_ACTIONS or sum(len(b['data']) for b in current_batch) >= MAX_BATCH_BYTES:
            current_batch = []
            batches.append(current_batch)
        current_batch.append(block)
    
    return batches

def is_expected_upload_error(e: Exception) -> bool:
    return "Cannot find contract code for account" in str(e) or "Contract method is not found" in str(e)

async def upload_blocks(blocks: List[Dict[str, Any]], account: Account, options: Dict[str, Any] = DEFAULT_OPTIONS) -> None:
    log, status_callback = options["log"], options["status_callback"]
    account_id = options["account_id"]

    THROTTLE_S = 0.025
    blocks_and_status = []
    for i, block in enumerate(blocks):
        await asyncio.sleep(i * THROTTLE_S)
        uploaded = await is_already_uploaded(block['cid'], account, options)
        blocks_and_status.append({**block, 'uploaded': uploaded})
    
    filtered_blocks = [block for block in blocks_and_status if not block['uploaded']]
    batches = split_on_batches(filtered_blocks)
    
    total_blocks = sum(len(batch) for batch in batches)
    current_blocks = 0
    
    for batch in batches:
        try:
            actions = [
                create_function_call_action(
                    'fs_store',
                    block['data'],  # Pass only the block data
                    30_000_000_000_000,  # 30 TGas
                    0
                )
                for block in batch
            ]

            outcome = await account.sign_and_submit_tx(
                receiver_id=account_id,
                actions=actions
            )
            log(f"Transaction hash: {outcome.transaction.hash}")
        except Exception as e:
            if not is_expected_upload_error(e):
                log(f"Error uploading batch: {str(e)}")
                raise
        
        current_blocks += len(batch)
        log(f"Uploaded {current_blocks} / {total_blocks} blocks to NEARFS")
        status_callback(current_blocks, total_blocks)

async def upload_files(files: List[Dict[str, Any]], options: Dict[str, Any] = DEFAULT_OPTIONS) -> str:
    log = options["log"]
    account_id = options["account_id"]
    private_key = options["private_key"]
    network_id = options["network_id"]
    
    if not account_id or not private_key:
        raise ValueError("account_id and private_key must be provided in options")
    
    account = Account(account_id, private_key, rpc_addr=f"https://rpc.{network_id}.near.org")
    print('upload_files', files, options)
    
    root_dir = {"name": "", "links": []}
    blocks_to_upload = []

    for file in files:
        path = file["name"].split(os.path.sep)
        dir_node = root_dir
        for i in range(len(path) - 1):
            dir_name = path[i]
            dir_entry = next((entry for entry in dir_node["links"] if entry["name"] == dir_name), None)
            if not dir_entry:
                dir_entry = {"name": dir_name, "links": []}
                dir_node["links"].append(dir_entry)
            dir_node = dir_entry

        file_name = path[-1]
        content = file["content"]
        hash_ = compute_hash(content)
        cid = pack_cid({'version': 1, 'codec': 0x55, 'hashType': 0x12, 'hash': hash_})
        file_entry = {"name": file_name, "cid": cid, "size": len(content)}
        dir_node["links"].append(file_entry)
        blocks_to_upload.append({"data": content, "cid": cid})

    def add_blocks_for_dir(dir_node):
        for entry in dir_node["links"]:
            if "links" in entry:
                entry["cid"] = add_blocks_for_dir(entry)
        
        pb_node = write_pb_node({"links": dir_node["links"], "data": b'\x08\x01'})
        hash_ = compute_hash(pb_node)
        cid = pack_cid({'version': 1, 'codec': 0x70, 'hashType': 0x12, 'hash': hash_})
        blocks_to_upload.append({"data": pb_node, "cid": cid})
        return cid

    log("rootDir", root_dir)
    root_cid = add_blocks_for_dir(root_dir)
    log("rootCid", cid_to_string(root_cid))

    for block in blocks_to_upload:
        log("block", cid_to_string(block["cid"]))

    await upload_blocks(blocks_to_upload, account, options)

    return cid_to_string(root_cid)
import asyncio
from typing import List, Dict, Any
from py_near.account import Account
from py_near.dapps.core import NEAR
from ipfs_helpers import (
    compute_hash, cid_to_string, pack_cid, write_pb_node, read_cid
)

DEFAULT_OPTIONS = {
    "log": print,
    "status_callback": lambda current_blocks, total_blocks: None,
    "timeout": 2.5,
    "retry_count": 3,
    "gateway_url": "https://ipfs.web4.near.page",
    "account": None,  # This will now be an Account object
}

async def is_already_uploaded(cid: bytes, account: Account, options: Dict[str, Any] = DEFAULT_OPTIONS) -> bool:
    log, timeout, retry_count = options["log"], options["timeout"], options["retry_count"]
    cid32 = cid_to_string(cid)
    
    for _ in range(retry_count):
        try:
            result = await account.view_function("nearfs.near", "has_block", {"cid": cid32})
            if result:
                log(f"Block {cid32} already exists on chain, skipping")
                return True
        except Exception as e:
            log(f"Error checking block {cid32}: {str(e)}")
            await asyncio.sleep(1)
    
    return False

# ... [keep the split_on_batches function as is] ...

async def upload_blocks(blocks: List[Dict[str, Any]], account: Account, options: Dict[str, Any] = DEFAULT_OPTIONS) -> None:
    log, status_callback = options["log"], options["status_callback"]
    
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
            tr = await account.function_call(
                "nearfs.near",
                "store",
                {"blocks": [cid_to_string(b['cid']) for b in batch]},
                300 * 10**12,  # 300 TGas
                0  # Deposit
            )
            log(f"Transaction hash: {tr.transaction.hash}")
        except Exception as e:
            log(f"Error uploading batch: {str(e)}")
        
        current_blocks += len(batch)
        log(f"Uploaded {current_blocks} / {total_blocks} blocks to NEARFS")
        status_callback(current_blocks, total_blocks)

async def upload_files(files: List[Dict[str, Any]], options: Dict[str, Any] = DEFAULT_OPTIONS) -> str:
    log = options["log"]
    account = options["account"]
    
    if not account:
        raise ValueError("account must be provided in options")
    
    await account.startup()
    
    blocks_to_upload = []
    for file in files:
        content = file["content"]
        hash_ = compute_hash(content)
        cid = pack_cid({'version': 1, 'codec': 0x55, 'hashType': 0x12, 'hash': hash_})
        blocks_to_upload.append({"data": content, "cid": cid})

    # Create a root directory node
    root_links = [
        {
            "name": file["name"],
            "cid": block["cid"],
            "size": len(block["data"])
        }
        for file, block in zip(files, blocks_to_upload)
    ]
    root_node = {"links": root_links, "data": b'\x08\x01'}  # UnixFS directory type
    root_pb_node = write_pb_node(root_node)
    root_hash = compute_hash(root_pb_node)
    root_cid = pack_cid({'version': 1, 'codec': 0x70, 'hashType': 0x12, 'hash': root_hash})
    blocks_to_upload.append({"data": root_pb_node, "cid": root_cid})

    log("rootCid", cid_to_string(root_cid))
    
    for block in blocks_to_upload:
        log("block", cid_to_string(block["cid"]))
    
    await upload_blocks(blocks_to_upload, account, options)
    
    return cid_to_string(root_cid)

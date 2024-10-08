import asyncio
import os
import argparse
from typing import List, Dict, Any
from py_near.account import Account
from py_near.providers import JsonProvider
from nearfs_upload import upload_files, DEFAULT_OPTIONS

NETWORK_URLS = {
    'mainnet': 'https://rpc.mainnet.near.org',
    'testnet': 'https://rpc.testnet.near.org',
}

def get_network(account_id: str, network_arg: str = None) -> str:
    if network_arg:
        return network_arg
    if 'NEAR_ENV' in os.environ:
        return os.environ['NEAR_ENV']
    if 'NODE_ENV' in os.environ:
        return os.environ['NODE_ENV']
    if account_id.endswith('.near'):
        return 'mainnet'
    return 'testnet'

async def main(args):
    account_id = args.account_id
    network = get_network(account_id, args.network)
    
    signer_account_id = os.environ.get('NEAR_SIGNER_ACCOUNT', account_id)
    signer_private_key = os.environ.get('NEAR_SIGNER_KEY') or os.environ.get('NEAR_PRIVATE_KEY')

    if not signer_private_key:
        raise ValueError("NEAR_SIGNER_KEY or NEAR_PRIVATE_KEY environment variable is not set")

    options = {
        **DEFAULT_OPTIONS,
        "account_id": signer_account_id,
        "private_key": signer_private_key,
    }

    # Set up the network provider
    if network not in NETWORK_URLS:
        raise ValueError(f"Unsupported network: {network}")
    provider = JsonProvider(NETWORK_URLS[network])
    
    # Create the account with the correct network provider
    account = Account(signer_account_id, signer_private_key, provider=provider)
    options["account"] = account

    files: List[Dict[str, Any]] = []
    for file_path in args.files:
        with open(file_path, 'rb') as f:
            content = f.read()
        files.append({"name": os.path.basename(file_path), "content": content})
    
    root_cid = await upload_files(files, options)
    print(f"Uploaded files with root CID: {root_cid}")
    print(f"Network: {network}")
    print(f"Signer Account: {signer_account_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload files to NEARFS")
    parser.add_argument("account_id", help="Your NEAR account ID")
    parser.add_argument("files", nargs="+", help="Files to upload")
    parser.add_argument("--network", choices=['mainnet', 'testnet'], help="NEAR network to use")
    args = parser.parse_args()
    
    asyncio.run(main(args))

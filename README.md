# NEARFS File Uploader

This Python tool simplifies the process of uploading files to **NEARFS** (NEAR File System). It streamlines file handling by splitting large files into smaller blocks, encoding data, calculating hashes, and seamlessly managing interactions with the NEAR blockchain. While the project itself doesn't directly utilize IPFS, it's worth noting that **NEARFS maintains URL and content compatibility with IPFS**, ensuring smooth interoperability.

## Getting Started

### Prerequisites

*   **Python 3.7 or higher**: Make sure you have a compatible Python version installed.
*   **Python Libraries**: Install the necessary Python libraries using `pip install -r requirements.txt`. The `requirements.txt` file should list:
    *   `py_near`: For interacting with the NEAR blockchain.
    *   `aiohttp`:  For handling asynchronous HTTP requests, particularly when checking for existing uploads.
*   **NEAR Development Environment (Optional):**  Having a NEAR development environment set up can be beneficial for testing and deploying your project, especially if you're working with testnets.

### Installation

1.  **Clone the Repository:** Clone this repository to your local machine using: `git clone <repository_url>`
2.  **Navigate to Directory:** In your terminal, navigate to the project's root directory: `cd <your-repo-name>`
3.  **Install Dependencies:** Install the required Python libraries from the `requirements.txt` file: `pip install -r requirements.txt` 

### Configuration

*   **Environment Variables**: Configure the following environment variables to manage NEAR account credentials and specify the network:
    *   `NEAR_SIGNER_ACCOUNT`: Your NEAR account ID. Used for signing transactions and interacting with the blockchain.
    *   `NEAR_SIGNER_KEY`: Your NEAR signer key. 
    *   `NEAR_PRIVATE_KEY`: Your NEAR private key. Can be used as an alternative to `NEAR_SIGNER_KEY`.
    *   `NEAR_ENV`:  Specifies the NEAR network environment. Options are `mainnet` or `testnet`. This determines which network the uploader interacts with.
*   **Credentials File (Alternative):**  As an alternative to setting environment variables, you can store your NEAR credentials in the `~/.near-credentials/<network>/<account_id>.json` file. This approach can be more secure.

## Usage

### Command-Line Interface

This project provides a command-line interface for easy interaction:

*   **File Input**: Specify the files you wish to upload using the `files` argument. Provide the paths to your desired files.
*   **Network Selection**:  Use the `--network` flag followed by either `mainnet` or `testnet` to choose the NEAR network you want to interact with.
*   **Account Identification**:  Provide your NEAR `account_id` as an argument. The tool will try to load account credentials from the environment variables or the `.near-credentials` file.

**Example Command:**

```bash
python cli.py <your-account-id> <file1> <file2> --network testnet
```

### Code Examples

The following code demonstrates how to upload files using the `upload_files` function:

```python
import asyncio
from nearfs_upload import upload_files

# Example file data
files = [
    {"name": "image.jpg", "content": open("image.jpg", "rb").read()},
    {"name": "document.pdf", "content": open("document.pdf", "rb").read()}
]

# Execute the asynchronous upload process
root_cid = asyncio.run(upload_files(files)) 

print(f"Uploaded files with root CID: {root_cid}")
```

**Explanation**

*   **File Preparation:** The code prepares a list called `files`, where each element is a dictionary containing the file's name and content.
*   **Asynchronous Upload:**  It uses `asyncio.run()` to execute the `upload_files` function, which is likely an asynchronous function.
*   **Root CID Output:** Finally, it prints the root CID returned by the `upload_files` function. This CID represents the root directory of the uploaded files on NEARFS.

## Contributing

We encourage contributions to enhance this project! If you're interested in contributing:

1.  **Fork the Repository:** Create a fork of this repository to your own GitHub account.
2.  **Branch Creation:**  Create a new branch for your feature or bug fix:  `git checkout -b <branch_name>`
3.  **Implement Changes**:  Make your desired code changes.
4.  **Commit and Push:** Commit your changes:  `git commit -m "Description of your changes"` and push them to your forked repository: `git push origin <branch_name>`.
5.  **Pull Request:** Open a pull request from your forked branch to the main repository's relevant branch.

## License

This project is licensed under the **MIT License**. Refer to the LICENSE file for the complete license text.
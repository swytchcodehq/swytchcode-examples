# GitHub Issue Integration Setup

This repository demonstrates how to use the Swytchcode CLI and TypeScript SDK to interact with the GitHub API to dynamically create issues.

## Prerequisites
- Node.js (v18 or higher)
- A GitHub account

## Setup Instructions

### 1. Install Swytchcode CLI
First, install the Swytchcode CLI globally on your machine:
```bash
npm install -g swytchcode
```

### 2. Fork and Clone
Fork this repository to your own account, then clone it locally:
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/github-issue-swytchcode.git
cd github-issue-swytchcode
```

### 3. Install Dependencies
Install the local project packages and download the Swytchcode integration:
```bash
npm install
swytchcode bootstrap
```

### 4. Configure Environment
1. Copy the `.env.example` file to create a new `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Generate a Personal Access Token (PAT) with `repo` permissions:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Check the `repo` scope box
   - Generate and copy the token (starts with `ghp_`)
3. Open `.env` and paste your PAT.

### 5. Run the Script
Execute the main script:
```bash
npm run dev
```

The script automatically detects your forked repository URL and uses your PAT to create a test issue on it. Check the terminal output for the link to your newly created issue.

## Troubleshooting
- **GITHUB_PAT is not set:** Ensure you renamed `.env.example` to `.env`.
- **Could not read git remote:** Ensure you ran the script from inside the cloned git repository folder.
- **401 Unauthorized / Bad Credentials:** Your token may be invalid. Generate a new one and update `.env`.
- **404 Not Found / Permission Denied:** Ensure your token has the `repo` scope enabled.

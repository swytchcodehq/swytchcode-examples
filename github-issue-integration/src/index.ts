import { exec } from 'swytchcode-runtime';
import { execSync } from 'child_process';
import * as dotenv from 'dotenv';

dotenv.config();

async function main() {
  console.log('--- GitHub Issue Integration ---');
  
  // 1. Check for GitHub PAT
  const token = process.env.GITHUB_PAT;
  if (!token) {
    console.error('ERROR: GITHUB_PAT is not set in the .env file!');
    process.exit(1);
  }

  // 2. Dynamically identify the forked repo from local git config
  console.log('Detecting local git repository information...');
  let gitRemoteUrl = '';
  try {
    gitRemoteUrl = execSync('git config --get remote.origin.url', { encoding: 'utf-8' }).trim();
  } catch (err) {
    console.error('ERROR: Could not read git remote. Are you in a git repository?');
    process.exit(1);
  }

  console.log(`Found remote origin: ${gitRemoteUrl}`);

  // Parse owner and repo from URL
  // Matches: https://github.com/owner/repo.git or git@github.com:owner/repo.git
  const match = gitRemoteUrl.match(/github\.com[:/]([^/]+)\/(.+?)(?:\.git)?$/);
  if (!match) {
    console.error('ERROR: Could not parse GitHub owner and repo from the remote URL.');
    process.exit(1);
  }

  const owner = match[1];
  const repo = match[2];
  console.log(`Detected Owner: ${owner}, Repo: ${repo}`);

  if (owner.toLowerCase() === 'swytchcodehq') {
    console.error('\nERROR: You cloned the original "swytchcodehq" repository instead of your fork!');
    console.error('Please delete this folder, fork the repository on GitHub to your own account, and clone your fork instead.');
    process.exit(1);
  }

  const title = process.env.ISSUE_TITLE || 'Test Issue';
  const body = process.env.ISSUE_BODY || 'This issue was automatically created by running npm run dev.';

  console.log(`\nCreating issue "${title}" on ${owner}/${repo}...`);

  try {
    // 3. Execute Swytchcode GitHub Integration
    const result = await exec('repos.issue.create', {
      owner: owner,
      repo: repo,
      Authorization: `Bearer ${token}`,
      body: {
        title: title,
        body: body
      }
    }) as any;

    console.log('\nSuccess! Issue created.');
    console.log(`Issue URL: ${result.data.html_url}`);
    console.log(`Issue Number: #${result.data.number}`);
  } catch (error) {
    console.error('\n❌ Failed to create issue!');
    console.error('HINT: This usually happens if your GitHub PAT is invalid, expired, or missing the "repo" scope.');
    console.error('Make sure you copied the token correctly into the .env file.\n');
    console.error('Detailed Error:');
    console.error(error);
  }
}

main();

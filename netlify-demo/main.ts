import 'dotenv/config';
import { Agent, run } from '@openai/agents';
import { Swytchcode, TOOL_USE_INSTRUCTIONS } from '@swytchcode/runtime';
import { OpenAIAgentsProvider } from '@swytchcode/runtime/providers/openai-agents';

// 1. Initialize Swytchcode with the OpenAI Agents SDK provider
const swx = new Swytchcode(new OpenAIAgentsProvider());

async function runDemo() {
  // 2. Fetch the Netlify tools enabled in tooling.json
  const tools = await swx.tools.get({
    tools: [
      'netlify.site.create',
      'netlify.site.deploys.create',
      'netlify.build.status.get',
      'netlify.account.env.update',
      'netlify.site.publish.create',
      'netlify.site.rollback.update',
    ],
  });

  // 3. Build the agent: instructions plus TOOL_USE_INSTRUCTIONS, which tells
  // the model to call the tool directly for action requests instead of just
  // describing what it would do
  const agent = new Agent({
    name: 'Netlify Ops Assistant',
    instructions: `You are a Netlify operations assistant. You can create sites, trigger deploys, and check account build status.\n\n${TOOL_USE_INSTRUCTIONS}`,
    tools,
  });

  // 4. Run the agent - it decides which of the 3 operations to call and in
  // what order based on the prompt below
  const result = await run(
    agent,
    'Create a new Netlify site named "swytchcode-demo", then trigger a deploy for it on the "main" branch, then check the build status for the account that owns this site (use the account_id from the site creation result).',
  );

  console.log(result.finalOutput);
}

runDemo().catch((err) => {
  console.error(err);
  process.exit(1);
});

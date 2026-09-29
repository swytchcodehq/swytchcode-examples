/** @type {import('next').NextConfig} */
export default {
  // These run on the server and spawn the `swytchcode` CLI; keep them unbundled.
  serverExternalPackages: ["@swytchcode/runtime", "@openai/agents", "@openai/agents-core"],
};

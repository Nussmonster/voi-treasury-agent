/**
 * Cloudflare Worker — Claude API proxy for VOI Treasury Agent
 *
 * Deploy:
 *   1. Install Wrangler: npm install -g wrangler
 *   2. wrangler login
 *   3. wrangler deploy worker/agent-proxy.js --name vtag-agent-proxy
 *   4. wrangler secret put ANTHROPIC_API_KEY   (paste your key when prompted)
 *   5. Copy the deployed *.workers.dev URL into AGENT_PROXY_URL in both
 *      docs/index.html and frontend/index.html
 *
 * The worker adds the API key server-side so it is never exposed in the browser.
 */

const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";
const ALLOWED_ORIGIN = "*"; // tighten to your GitHub Pages domain in production

export default {
  async fetch(request, env) {
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response("Invalid JSON", { status: 400 });
    }

    // Basic validation — only allow the fields the frontend sends
    const allowed = { model: true, max_tokens: true, system: true, messages: true };
    const sanitized = Object.fromEntries(
      Object.entries(body).filter(([k]) => allowed[k])
    );

    const upstream = await fetch(ANTHROPIC_API, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify(sanitized),
    });

    const data = await upstream.json();

    return new Response(JSON.stringify(data), {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
      },
    });
  },
};

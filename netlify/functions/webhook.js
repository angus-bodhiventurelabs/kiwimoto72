/**
 * WebSub subscriber endpoint.
 *
 * GET  — hub sends a verification challenge; we echo it back to confirm the subscription.
 * POST — hub notifies us of new content; we fire the Netlify build hook to redeploy.
 *
 * Required env var:
 *   NETLIFY_BUILD_HOOK  — the build hook URL from Netlify → Site settings → Build hooks
 */

const https = require("https");
const http = require("http");

function triggerBuild(hookUrl) {
  return new Promise((resolve, reject) => {
    const mod = hookUrl.startsWith("https") ? https : http;
    const req = mod.request(hookUrl, { method: "POST" }, (res) => {
      res.resume();
      resolve(res.statusCode);
    });
    req.on("error", reject);
    req.end();
  });
}

exports.handler = async (event) => {
  // WebSub hub verification (GET with hub.challenge)
  if (event.httpMethod === "GET") {
    const params = event.queryStringParameters || {};
    const challenge = params["hub.challenge"];
    if (challenge) {
      console.log("WebSub verified for topic:", params["hub.topic"]);
      return {
        statusCode: 200,
        headers: { "Content-Type": "text/plain" },
        body: challenge,
      };
    }
  }

  // New content notification (POST) — trigger a rebuild
  if (event.httpMethod === "POST") {
    const hookUrl = process.env.NETLIFY_BUILD_HOOK;
    if (!hookUrl) {
      console.error("NETLIFY_BUILD_HOOK env var is not set");
      return { statusCode: 500, body: "Build hook not configured" };
    }
    try {
      const status = await triggerBuild(hookUrl);
      console.log("Build hook triggered, response status:", status);
      return { statusCode: 200, body: "Build triggered" };
    } catch (err) {
      console.error("Failed to trigger build hook:", err.message);
      return { statusCode: 500, body: "Failed to trigger build" };
    }
  }

  return { statusCode: 405, body: "Method not allowed" };
};

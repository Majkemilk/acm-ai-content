import { defineCloudflareConfig } from "@opennextjs/cloudflare";

export default defineCloudflareConfig({
  // No R2/KV required for minimal deploy; add incrementalCache when using R2
});

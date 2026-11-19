import { defineConfig } from "vite";

// Deny the API namespace before Vite's SPA fallback in both dev and preview.
// The UI serves local synthetic fixtures only and must never impersonate an API.
function denyApi(req: { url?: string }, res: {
  statusCode: number;
  setHeader(name: string, value: string): void;
  end(body: string): void;
}, next: () => void) {
  const path = (req.url || "").split("?", 1)[0];
  if (path === "/api" || path.startsWith("/api/")) {
    res.statusCode = 404;
    res.setHeader("Cache-Control", "no-store");
    res.end("Not found");
    return;
  }
  next();
}

export default defineConfig({
  plugins: [{
    name: "deny-all-api",
    configureServer(server) {
      server.middlewares.use(denyApi);
    },
    configurePreviewServer(server) {
      server.middlewares.use(denyApi);
    },
  }],
  server: { host: "127.0.0.1" },
  preview: { host: "127.0.0.1" },
});

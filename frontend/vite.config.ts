import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "PUBLIC_");
  process.env.PUBLIC_BROWSER_DEMO ??= env.PUBLIC_BROWSER_DEMO || "false";
  process.env.PUBLIC_DEV_LOGIN ??= env.PUBLIC_DEV_LOGIN || "false";
  return {
    plugins: [sveltekit()],
    server: {
      proxy: {
        "/api": process.env.SMT_API_PROXY || "http://127.0.0.1:8000",
        "/health": process.env.SMT_API_PROXY || "http://127.0.0.1:8000",
      },
    },
  };
});

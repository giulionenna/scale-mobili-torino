import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

process.env.PUBLIC_BROWSER_DEMO ??= 'false';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000'
    }
  }
});

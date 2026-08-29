import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/video_feed': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/alerts': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/anpr': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/anpr_debug': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
});

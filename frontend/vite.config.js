import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

const frontendDirectory = fileURLToPath(new URL('.', import.meta.url))
const sharedDirectory = fileURLToPath(new URL('../shared/', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const backendTarget = process.env.AI_KRUSHIMITRA_BACKEND_URL
    || env.VITE_API_BASE_URL
    || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      fs: {
        allow: [frontendDirectory, sharedDirectory]
      },
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true
        },
        '/socket.io': {
          target: backendTarget,
          changeOrigin: true,
          ws: true
        },
        '/ws': {
          target: backendTarget,
          changeOrigin: true,
          ws: true
        }
      }
    }
  }
})

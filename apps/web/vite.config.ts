import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // A tela chama /api/... e o Vite repassa para o servidor local, tirando o /api. Assim funciona
  // também pelo celular (--host) e sem mexer em CORS.
  server: {
    proxy: {
      '/api': {
        target: process.env.GARIMPO_API ?? 'http://127.0.0.1:8000',
        rewrite: (caminho) => caminho.replace(/^\/api/, ''),
      },
    },
  },
})

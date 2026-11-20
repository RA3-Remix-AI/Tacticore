import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Kept for the Windows build script; the default config now builds the same product entry.
// public/ is included so the commander portraits ship in the beta candidate build too.
export default defineConfig({
  plugins:[react(),{name:'native-beta-entry',transformIndexHtml(html){return html.replace('/src/main.tsx','/src/main.beta.tsx');}}],
  clearScreen:false,
});

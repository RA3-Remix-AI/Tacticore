import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins:[react(),{name:'native-beta-entry',transformIndexHtml(html){return html.replace('/src/main.tsx','/src/main.beta.tsx').replace('独立 Agent 指挥系统桌面交互演示。','Windows AI 指挥官 beta 客户端。');}}],
  publicDir:false,clearScreen:false,
});

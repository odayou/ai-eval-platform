import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// vite.config.ts 运行在 Node 中；这里只做类型声明，避免依赖 @types/node
declare const process: { env: Record<string, string | undefined> };

// 端口唯一来源：APP_PORT 环境变量（start.bat 会设置），默认 8001
const backendPort = process.env.APP_PORT || '8001';
const backendTarget = `http://127.0.0.1:${backendPort}`;

console.log(`[vite] 后端代理 /api -> ${backendTarget} (APP_PORT=${backendPort})`);
console.log(`[vite] 健康检查 ${backendTarget}/api/health`);
console.log('[vite] 监听 0.0.0.0:5173，局域网可通过本机 IP 访问（Vite 会打印 Network 地址）');

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': backendTarget,
      '/ws': { target: `ws://127.0.0.1:${backendPort}`, ws: true },
    },
  },
});

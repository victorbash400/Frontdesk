import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const extensionRoot = import.meta.dirname;

export default defineConfig(({ mode }) => {
  const cloudOrigin = process.env.VITE_FRONT_DESK_API_ORIGIN || '';
  const backendEnvironment = cloudOrigin ? {} : loadEnv(mode, resolve(extensionRoot, '../backend'), 'FRONT_DESK_');
  return {
    root: resolve(extensionRoot, 'src/ui'),
    publicDir: false,
    plugins: [react()],
    define: {
      'import.meta.env.FRONT_DESK_PLAYWRIGHT_EXTENSION_TOKEN': JSON.stringify(backendEnvironment.FRONT_DESK_PLAYWRIGHT_EXTENSION_TOKEN || ''),
    },
    build: {
      outDir: resolve(extensionRoot, 'dist'),
      emptyOutDir: true,
      minify: false,
      rollupOptions: {
        input: {
          connect: resolve(extensionRoot, 'src/ui/connect.html'),
          status: resolve(extensionRoot, 'src/ui/status.html'),
        },
        output: {
          entryFileNames: 'lib/ui/[name].js',
          chunkFileNames: 'lib/ui/[name].js',
          assetFileNames: 'lib/ui/[name].[ext]',
        },
      },
    },
  };
});

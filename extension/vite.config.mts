import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const extensionRoot = import.meta.dirname;

export default defineConfig(({ mode }) => {
  const cloudOrigin = process.env.VITE_FRONT_DESK_API_ORIGIN || '';
  // A loopback API origin is still a local build talking to the local backend, so it
  // needs that backend's connection token. Only a remote origin skips loading it.
  const remoteOrigin = cloudOrigin && !/^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:|$|\/)/.test(cloudOrigin);
  const backendEnvironment = remoteOrigin ? {} : loadEnv(mode, resolve(extensionRoot, '../backend'), 'FRONT_DESK_');
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

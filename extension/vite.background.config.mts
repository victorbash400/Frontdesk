import { resolve } from 'node:path';
import { defineConfig } from 'vite';

const extensionRoot = import.meta.dirname;

export default defineConfig({
  build: {
    outDir: resolve(extensionRoot, 'dist/lib'),
    emptyOutDir: false,
    minify: false,
    lib: {
      entry: resolve(extensionRoot, 'src/background.ts'),
      fileName: 'background',
      formats: ['es'],
    },
  },
});

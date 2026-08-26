import { resolve } from 'node:path';
import { defineConfig } from 'vite';

const extensionRoot = import.meta.dirname;

export default defineConfig({
  build: {
    outDir: resolve(extensionRoot, 'dist/lib'),
    emptyOutDir: false,
    minify: false,
    lib: {
      entry: {
        background: resolve(extensionRoot, 'src/background.ts'),
        content: resolve(extensionRoot, 'src/content.ts'),
      },
      fileName: (_format, entryName) => entryName === 'background' ? 'background.mjs' : 'content.js',
      formats: ['es'],
    },
  },
});

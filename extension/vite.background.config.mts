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
        meetAgent: resolve(extensionRoot, 'src/meetAgent.ts'),
        meetRelay: resolve(extensionRoot, 'src/meetRelay.ts'),
        offscreen: resolve(extensionRoot, 'src/offscreen.ts'),
      },
      fileName: (_format, entryName) => entryName === 'background' ? 'background.mjs' : `${entryName}.js`,
      formats: ['es'],
    },
  },
});

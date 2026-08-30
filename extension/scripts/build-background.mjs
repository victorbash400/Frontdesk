import { resolve } from 'node:path';
import { build } from 'vite';

const root = resolve(import.meta.dirname, '..');
for (const entry of ['background', 'content', 'meetAgent', 'meetRelay', 'offscreen']) {
  // Content scripts are not modules: each entry must have a standalone bundle.
  await build({
    configFile: false,
    root,
    build: {
      outDir: resolve(root, 'dist/lib'),
      emptyOutDir: false,
      minify: false,
      lib: {
        entry: resolve(root, `src/${entry}.ts`),
        name: `FrontDesk_${entry}`,
        formats: [entry === 'background' || entry === 'offscreen' ? 'es' : 'iife'],
        fileName: () => entry === 'background' ? 'background.mjs' : `${entry}.js`,
      },
    },
  });
}

import { cp, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const extensionRoot = resolve(import.meta.dirname, '..');
const outputRoot = resolve(extensionRoot, 'dist');

await mkdir(resolve(outputRoot, 'icons'), { recursive: true });
await cp(resolve(extensionRoot, 'manifest.json'), resolve(outputRoot, 'manifest.json'));
await cp(resolve(extensionRoot, 'icons'), resolve(outputRoot, 'icons'), { recursive: true });

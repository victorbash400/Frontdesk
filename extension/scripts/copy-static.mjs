import { cp, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const extensionRoot = resolve(import.meta.dirname, '..');
const outputRoot = resolve(extensionRoot, 'dist');

await mkdir(resolve(outputRoot, 'icons'), { recursive: true });
await cp(resolve(extensionRoot, 'manifest.json'), resolve(outputRoot, 'manifest.json'));
await cp(resolve(extensionRoot, 'icons'), resolve(outputRoot, 'icons'), { recursive: true });
await cp(resolve(extensionRoot, 'cursor-alt-svgrepo-com.svg'), resolve(outputRoot, 'cursor-alt-svgrepo-com.svg'));
await cp(resolve(extensionRoot, 'offscreen.html'), resolve(outputRoot, 'offscreen.html'));
await cp(resolve(extensionRoot, 'audio-input-processor.js'), resolve(outputRoot, 'lib/audio-input-processor.js'));
await cp(resolve(extensionRoot, 'audio-output-processor.js'), resolve(outputRoot, 'lib/audio-output-processor.js'));

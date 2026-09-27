import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { installationHint } from './help.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { version } = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
const command = process.env.npm_config_global === 'true' ? 'soda'
  : process.env.INIT_CWD && path.resolve(process.env.INIT_CWD) === root ? 'node bin/soda.js'
    : 'npx soda';
process.stdout.write(installationHint(version, command));

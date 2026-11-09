// Fails if any modules in site/js import each other in a loop (directly or through other modules).
// The app is layered so every import points "down"; see "How the app works" in DEVELOPMENT.md.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const dir = 'site/js';
const graph = new Map();
for (const file of readdirSync(dir).filter(f => f.endsWith('.js'))) {
  const src = readFileSync(join(dir, file), 'utf8');
  const deps = [...src.matchAll(/^import\s[^;]*?['"]\.\/([\w.-]+\.js)['"]/gm)].map(m => m[1]);
  graph.set(file, [...new Set(deps)]);
}

const cycles = [];
const state = new Map(); // file -> 'visiting' | 'done'
function visit(file, path) {
  if (state.get(file) === 'done') return;
  if (state.get(file) === 'visiting') {
    cycles.push([...path.slice(path.indexOf(file)), file].join(' → '));
    return;
  }
  state.set(file, 'visiting');
  for (const dep of graph.get(file) ?? []) visit(dep, [...path, file]);
  state.set(file, 'done');
}
for (const file of graph.keys()) visit(file, []);

if (cycles.length) {
  console.error(`Import loops in ${dir}:\n${cycles.map(c => '  ' + c).join('\n')}`);
  process.exit(1);
}
console.log(`No import loops in ${dir} (${graph.size} modules).`);

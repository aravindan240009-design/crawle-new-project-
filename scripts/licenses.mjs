import fs from 'node:fs'
import path from 'node:path'
const root = path.resolve(import.meta.dirname, '..')
const rows = new Map()
function packages(directory) {
  if (!fs.existsSync(directory)) return
  for (const name of fs.readdirSync(directory)) {
    if (name.startsWith('.')) continue
    const location = path.join(directory, name)
    if (name.startsWith('@')) { packages(location); continue }
    const manifest = path.join(location, 'package.json')
    if (!fs.existsSync(manifest)) continue
    const p = JSON.parse(fs.readFileSync(manifest, 'utf8'))
    rows.set(p.name + '@' + p.version, [p.name, p.version, typeof p.license === 'string' ? p.license : JSON.stringify(p.license || 'Check package LICENSE')])
    packages(path.join(location, 'node_modules'))
  }
}
packages(path.join(root, 'frontend', 'node_modules'))
const output = '# Frontend dependency licenses\n\nGenerated from installed locked package metadata on 2026-10-09. Includes development tools. See package LICENSE files for full terms.\n\n| Package | Version | License |\n|---|---|---|\n' + [...rows.values()].sort().map(row => '| ' + row.join(' | ') + ' |').join('\n') + '\n'
fs.writeFileSync(path.join(root, 'docs', 'FRONTEND_LICENSES.md'), output)
console.log(`Recorded ${rows.size} package license entries`)

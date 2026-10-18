import { defineConfig } from '@playwright/test'
import path from 'node:path'

const root = path.resolve('..')
const python = process.platform === 'win32' ? path.join(root, '.venv', 'Scripts', 'python.exe') : path.join(root, '.venv', 'bin', 'python')
export default defineConfig({
  testDir: './e2e', timeout: 45000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:8766', viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure' },
  webServer: {
    command: `"${python}" -m backend serve`, cwd: root, url: 'http://127.0.0.1:8766/api/health', reuseExistingServer: false,
    env: { RADAR_FIXTURES: '1', RADAR_PORT: '8766', RADAR_DATA_DIR: path.join(root, 'data', 'e2e-' + Date.now()) },
  },
})

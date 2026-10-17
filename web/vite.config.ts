import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig, type Plugin } from 'vite'
import fs from 'node:fs'
import path from 'node:path'

const DATA_DIR = path.resolve(__dirname, '../docs/data')

/** Dev only: serve ../docs/data at /data/ with HTTP range support (as GitHub Pages does). */
function serveData(): Plugin {
  return {
    name: 'serve-docs-data',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0]
        if (!url.startsWith('/data/')) return next()
        const file = path.join(DATA_DIR, decodeURIComponent(url.slice('/data/'.length)))
        if (!file.startsWith(DATA_DIR) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
          res.statusCode = 404
          return res.end('not found')
        }
        const size = fs.statSync(file).size
        const range = /bytes=(\d*)-(\d*)/.exec(req.headers.range ?? '')
        res.setHeader('Accept-Ranges', 'bytes')
        res.setHeader('Access-Control-Allow-Origin', '*')
        if (url.endsWith('.json')) res.setHeader('Content-Type', 'application/json')
        if (range) {
          const start = range[1] ? parseInt(range[1]) : size - parseInt(range[2])
          const end = range[1] && range[2] ? Math.min(parseInt(range[2]), size - 1) : size - 1
          res.statusCode = 206
          res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`)
          res.setHeader('Content-Length', end - start + 1)
          fs.createReadStream(file, { start, end }).pipe(res)
        } else {
          res.setHeader('Content-Length', size)
          fs.createReadStream(file).pipe(res)
        }
      })
    },
  }
}

export default defineConfig({
  // Relative base so the site works under https://<user>.github.io/<repo>/ and locally.
  base: './',
  plugins: [svelte(), serveData()],
  build: {
    outDir: '../docs',
    emptyOutDir: false, // never delete docs/data
    chunkSizeWarningLimit: 6000,
    assetsInlineLimit: 0,
  },
  optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] },
})

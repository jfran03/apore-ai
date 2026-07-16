# Apore Client

React + TypeScript + Vite hub. Builds for web (Vite) and desktop (Tauri).

## Web development

```bash
npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # production build → dist/
```

## Desktop build (Tauri)

**Prerequisites:**
- Rust (https://rustup.rs) — install with `rustup`
- Windows: WebView2 (bundled with Windows 10/11 since April 2021)
- Node 18+

**First time:**
```bash
npm install
# Rust must be installed first (rustup.rs)
```

**Build:**
```bash
npm run tauri:build    # produces installer in src-tauri/target/release/bundle/
```

**Dev mode (app + API in two terminals):**
```
Terminal 1: cd program && uvicorn apore.api.app:app --reload --port 8000
Terminal 2: cd program/client && npm run tauri:dev
```

## API base URL

The app reads `VITE_API_BASE_URL` at build time (defaults to `http://localhost:8000`).
For a packaged desktop app pointing at a remote API:
```bash
VITE_API_BASE_URL=https://your-api-host npm run tauri:build
```

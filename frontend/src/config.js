// The backend's base URL. Locally this falls back to localhost, matching
// how the app has always run in dev. In production (Netlify), VITE_API_URL
// is set at build time to the real deployed backend's URL (see
// README/deployment notes) -- Vite bakes env vars starting with VITE_ into
// the build, so this is resolved once at build time, not read at runtime.
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

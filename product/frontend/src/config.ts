// API base URL. In dev and packaged desktop builds the backend runs locally on
// :8000. A build-time override is supported for pointing at a remote API.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

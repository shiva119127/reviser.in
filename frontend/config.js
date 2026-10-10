/**
 * YT Reviser - Frontend Runtime Configuration
 *
 * When deploying the frontend to Vercel, Netlify, or custom hosting:
 * Set apiBaseUrl to your deployed backend API URL
 * (e.g. "https://yt-reviser-api.onrender.com" or "https://your-railway-app.up.railway.app").
 *
 * Note: If left as null, it will automatically use:
 * 1. Saved URL in Settings modal (stored in localStorage)
 * 2. http://127.0.0.1:8000 when running locally on localhost
 * 3. The current domain origin (window.location.origin) when served by FastAPI
 */
window.YT_REVISER_CONFIG = {
    apiBaseUrl: null
};

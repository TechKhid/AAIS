# Deploying AAIS to Fly.io and Vercel

This setup runs the FastAPI backend on Fly.io and serves the static command-center frontend from Vercel.

## Architecture

- Fly.io hosts `app.main:app` in a Docker container on port `8080`.
- Vercel builds a static bundle from `app/static` into `dist`.
- The browser reads `window.AAIS_CONFIG.apiBaseUrl` from `/static/config.js`.
- Backend CORS is controlled by `AAIS_CORS_ORIGINS`.

## Backend: Fly.io

1. Pick a globally unique Fly app name and update `fly.toml`:

```toml
app = "your-aais-backend"
```

2. Replace the placeholder CORS origin in `fly.toml` once you know the Vercel URL:

```toml
AAIS_CORS_ORIGINS = "https://your-vercel-project.vercel.app"
```

For a quick first smoke test, you can temporarily use `AAIS_CORS_ORIGINS = "*"`. Use exact origins for a shared demo or production-like deployment.

3. Create the Fly app without deploying yet:

```cmd
fly launch --copy-config --name your-aais-backend --no-deploy --no-db
```

4. Set the hosted NVIDIA NIM API key as a Fly secret:

```cmd
fly secrets set NVIDIA_NIM_API_KEY=<your NVIDIA API key>
```

5. Deploy:

```cmd
fly deploy
```

6. Smoke-check the backend:

```cmd
curl https://your-aais-backend.fly.dev/live
curl https://your-aais-backend.fly.dev/health
```

`/live` is the platform liveness check. `/health` also verifies the configured LLM provider and may report `llm_available: false` if the NIM key or model is wrong.

## Frontend: Vercel

1. Link the project from the repository root:

```cmd
vercel
```

The root `vercel.json` uses:

- `buildCommand`: `node scripts/build_frontend.mjs`
- `outputDirectory`: `dist`
- no frontend framework preset

2. Add the Fly backend URL as a production environment variable:

```cmd
echo https://your-aais-backend.fly.dev | vercel env add AAIS_API_BASE_URL production
```

3. Deploy production:

```cmd
vercel --prod
```

4. If the production Vercel URL differs from the one in `fly.toml`, update `AAIS_CORS_ORIGINS` and redeploy Fly:

```cmd
fly deploy
```

## Local Static Build Check

To verify the same frontend bundle locally:

```cmd
set "AAIS_API_BASE_URL=http://127.0.0.1:8000"
node scripts\build_frontend.mjs
```

The generated files land in `dist/`.

## Current MVP Caveats

- App state is in memory, so Fly restarts reset incidents, sessions, events, hospital capacity changes, and ambulance status.
- The frontend is public unless Vercel deployment protection is enabled.
- This simulator is not ready for real clinical PHI. Add authentication, durable storage, audit logging, and stricter CORS/domain controls before real pilots.

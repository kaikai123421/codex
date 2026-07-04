# Render Free + Neon/Supabase Free Deployment

This setup runs the DSA web app on Render free and stores durable data in a free Postgres database.

Why this architecture:

- Render free web services use an ephemeral filesystem, so local SQLite files can be lost after redeploys/restarts.
- Render free web services cannot attach persistent disks.
- Render free Postgres is not ideal for long-term use because free databases expire.
- Neon/Supabase free Postgres is a better fit for this small private trading dashboard.

Official references:

- Render free services: https://render.com/docs/free
- Render disks: https://render.com/docs/disks
- Neon pricing: https://neon.com/pricing
- Supabase pricing: https://supabase.com/pricing

## 1. Create a free cloud database

Use Neon or Supabase and create a Postgres project. Copy the pooled connection string and convert it to SQLAlchemy format:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require
```

## 2. Deploy on Render

Open:

```text
https://dashboard.render.com/blueprint/new?repo=https://github.com/kaikai123421/codex
```

Select the `render.yaml` blueprint from the repo root.

## 3. Fill Render environment secrets

Required:

- `DATABASE_URL`: the Neon/Supabase connection string.
- At least one AI key for analysis, for example `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`.

Recommended:

- `TUSHARE_TOKEN`
- `FINNHUB_API_KEY`
- `BRAVE_API_KEYS`

## 4. First login

Open the Render URL. Because `ADMIN_AUTH_ENABLED=true`, the first visit asks you to set the admin password.

Use a stronger password than `666666` if friends can access the URL.

## 5. Privacy notes

The URL is public, but the app requires a password. Anyone who knows the password can use the same account and data. For friends, prefer a future read-only/demo account.

# Free private deployment: Cloudflare Tunnel

This is the recommended free deployment path for the DSA web app.

## What this gives you

- Free remote access while your Windows machine is on.
- Your real data stays on this machine.
- No GitHub Pages/Vercel-style static hosting mismatch.
- App-level password protection stays enabled through `ADMIN_AUTH_ENABLED=true`.

## Important limits

- The computer must stay on, and the DSA server must keep running.
- A quick tunnel URL is reachable from the internet if someone gets the URL, so the DSA admin password is still required.
- For stronger access control, use a Cloudflare domain plus Cloudflare Access. Cloudflare Zero Trust has a free tier for small teams, but setup requires your domain in Cloudflare.

## Option A: no domain, fastest free test

1. Install `cloudflared` from Cloudflare.
2. Start the private local web server:

```powershell
cd D:\codex项目文件\gitup\github
.\scripts\start_private_web.ps1
```

3. Open a second PowerShell window and start the tunnel:

```powershell
cd D:\codex项目文件\gitup\github
.\scripts\start_cloudflare_quick_tunnel.ps1
```

4. Cloudflare prints a temporary `https://*.trycloudflare.com` URL.
5. Open that URL. On first visit, create the DSA admin password.

## Option B: domain + Cloudflare Access

Use this when you want "only I can open it" instead of "people need the URL and password".

1. Put your domain on Cloudflare.
2. Create a Cloudflare Zero Trust team.
3. Create a Tunnel pointing to `http://127.0.0.1:8000`.
4. Create an Access application for the hostname.
5. Allow only your email address.
6. Keep `ADMIN_AUTH_ENABLED=true` as a second lock.

## Why not Render as the default free path

Render can run free web services, but free instances have limits and their filesystem is ephemeral. This app stores local portfolio data, sessions, and reports, so a pure free Render deploy is only suitable for preview/testing unless you move persistence to a durable database.

The root `render.yaml` is kept as a free preview blueprint only. It should not be used as the main private trading journal until persistence is redesigned.

## Safety checklist before exposing the app

- `ADMIN_AUTH_ENABLED=true`
- Do not upload `.env`
- Do not upload `data/`, `logs/`, or `reports/`
- Use a strong admin password
- Prefer Cloudflare Access if the URL will be long-lived

# Hosting podpull.xiaolei.work (Vercel + Cloudflare)

Official site: **https://podpull.xiaolei.work**

- `/` — marketing landing  
- `/app` — interactive UI (search / trending / per-episode browser download)  
- `/api/*` — metadata only (no audio proxy)

Sources of truth in this repo:

| Edit this | Deployed as |
|-----------|-------------|
| `docs/index.html` (+ icons in `docs/`) | `public/index.html` |
| `src/podpull/serve/static/` | `public/app/` (+ shared icons) |
| `api/index.py` | Vercel Python function (`BaseHTTPRequestHandler`, stdlib + `podpull.serve`) |

Sync before local preview or as the Vercel `buildCommand`:

```bash
python3 scripts/sync_web_public.py
```

## Deploy (Vercel)

Project already created: **`xiaoleiys-projects/podpull`** (production alias: https://podpull.vercel.app).

CLI redeploy (from a machine logged into that team):

```bash
python3 scripts/sync_web_public.py
vercel deploy --prod --yes --scope xiaoleiys-projects
```

Optional: connect the GitHub repo in the Vercel dashboard (Project → Settings → Git) so pushes to `main` auto-deploy. The CLI `vercel git connect` needs the Vercel GitHub app installed on `xiaoleiy/podpull`.

## DNS (Cloudflare) — podpull.xiaolei.work

Live record (DNS only / grey cloud):

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| **CNAME** | `podpull` | `f59d5642c46f87ba.vercel-dns-017.com` | **DNS only** |

This is Vercel’s recommended target for the project (preferred over the generic `76.76.21.21` A).
Keep **DNS only** so Vercel terminates TLS.

```bash
dig +short podpull.xiaolei.work CNAME
curl -sS https://podpull.xiaolei.work/api/health
```

Vercel project: `xiaoleiys-projects/podpull` · also https://podpull.vercel.app

After DNS propagates, check:

- https://podpull.xiaolei.work/
- https://podpull.xiaolei.work/app
- https://podpull.xiaolei.work/api/health

## Local twin

```bash
podpull serve   # same UI/API contract on localhost
```

Audio always downloads from the publisher CDN in the browser — neither Vercel nor `serve` proxies episode bytes.

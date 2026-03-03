# kiwimoto77_website

Minimal static website with markdown blog posts built by Python and deployed on Netlify.

## Project structure

- `src/` - static frontend files (`index.html`, `styles.css`, `main.js`)
- `content/posts/` - blog posts in markdown
- `templates/` - HTML template for blog posts
- `scripts/build.py` - build script to generate static site
- `dist/` - generated output for deployment

## Homepage editing workflow

- Edit root `index.html` for your main homepage changes.
- On build, `scripts/build.py` copies files from `src/` and then uses root `index.html` (if present) as the final `dist/index.html`.
- This lets you keep your current editing workflow while still using the same Netlify build process.

## Local setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Build site:

   ```bash
   python scripts/build.py
   ```

4. Serve `dist/` locally (optional):

   ```bash
   cd dist && python -m http.server 8000
   ```

## GitHub integration

1. Initialize and push repository:

   ```bash
   git init
   git add .
   git commit -m "Initial website scaffold"
   git branch -M main
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. Keep Netlify connected to this GitHub repository.

## Netlify deployment

- Build command: `python scripts/build.py`
- Publish directory: `dist`
- These are already defined in `netlify.toml`.

In Netlify:
1. New site from Git -> choose GitHub repo.
2. Confirm build settings above.
3. Deploy.

## Squarespace domain setup

In Squarespace domain DNS settings, point the domain to Netlify:

1. Add/verify Netlify DNS records shown in your Netlify domain setup page.
2. Typical setup includes:
   - `A` records for apex/root domain pointing to Netlify load balancer IPs.
   - `CNAME` for `www` pointing to your Netlify subdomain.
3. In Netlify, add both custom domains (root and `www`) and set primary domain.
4. Wait for DNS propagation and enable HTTPS in Netlify.

Always use the exact DNS values shown by Netlify for your site, since they can vary.

## Automatic podcast updates

The homepage podcast cards can auto-refresh at build time from your podcast RSS feed.

- The build script first checks `PODCAST_RSS_URL`.
- If not set, it tries to auto-discover an RSS URL from `PODCAST_SITE_URL`.
- If `PODCAST_SITE_URL` is not set, it defaults to `https://kiwimoto72.buzzsprout.com`.

### Netlify environment variables (recommended)

In Netlify Site settings -> Environment variables:

- `PODCAST_RSS_URL` = your direct RSS URL (most reliable)
- optional: `PODCAST_SITE_URL` = your podcast landing page URL

If `PODCAST_RSS_URL` is set, it takes priority over auto-discovery.

## Automatic YouTube video updates

The homepage video cards auto-refresh at build time from your channel's uploads.

Requires a free YouTube Data API v3 key (~2 quota units per build; free tier is 10,000/day).

### Getting a YouTube API key

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or select an existing one)
3. **APIs & Services** → **Enable APIs** → search for **YouTube Data API v3** → Enable
4. **APIs & Services** → **Credentials** → **Create credentials** → **API key**
5. Copy the key

### Netlify environment variables

In Netlify Site settings → Environment variables:

- `YOUTUBE_API_KEY` = your API key (required)

Once set, each build fetches the 3 most recent videos from your channel and replaces the video cards automatically.

# Lab Report Generator — PDF Compile Backend

A small Flask API that compiles the LaTeX produced by `labweb.html` into a
real PDF using `pdflatex`, and streams the PDF back to the browser. This
powers the **"Generate PDF"** button — the `.tex`/`.zip` download + Overleaf
path still works as a fallback if this backend is ever unreachable.

## What it does

- `GET /health` — used by the frontend to check whether the backend is
  reachable and whether `pdflatex` is actually installed.
- `POST /compile` — accepts the generated LaTeX source (plus any output
  screenshots and the logo image as base64), runs `pdflatex` twice in a
  throwaway temp directory, and returns the resulting PDF. If compilation
  fails, it returns the relevant error from the LaTeX log instead of a PDF.

---

## 🚀 Deploying to Render (recommended, free to start)

This is the easiest path since this backend needs `pdflatex`, which Render's
plain Python runtime doesn't include — we use Docker instead, which lets us
install a full TeX Live distribution.

### Step 1 — Put this project on GitHub
1. Create a new GitHub repository (public or private, both work).
2. Push this whole folder structure to it:
   ```
   your-repo/
     labweb.html
     render.yaml
     backend/
       app.py
       requirements.txt
       Dockerfile
   ```
   If you don't already use git:
   ```bash
   cd your-project-folder
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

### Step 2 — Create the Render account & service
1. Go to **render.com** → sign up (GitHub login is fastest).
2. Click **New +** → **Blueprint**.
3. Connect your GitHub account and select the repo you just pushed.
4. Render will detect `render.yaml` automatically and show you the
   `lab-report-backend` service it's about to create. Click **Apply**.
5. Render builds the Docker image (installing TeX Live — this first build
   takes a few minutes, that's normal) and deploys it.
6. Once it's live, Render shows you a URL like:
   ```
   https://lab-report-backend.onrender.com
   ```
   **Copy this URL.**

### Step 3 — Point the frontend at your backend
1. Open `labweb.html` in a text editor.
2. Find this line near the top of the `<script>` section:
   ```js
   var DEFAULT_BACKEND_URL = 'https://lab-report-backend.onrender.com';
   ```
3. Replace it with **your actual Render URL** from Step 2.
4. Save the file. That's it — students who open this `labweb.html` (or who
   visit it if you also host it somewhere) will automatically use your
   deployed backend for the "Generate PDF" button.

### Step 4 — Test it
1. Open `labweb.html` in a browser.
2. Fill in the form, generate the LaTeX, then click **Generate PDF**.
3. First request after a period of inactivity may take 30–60 seconds
   (Render's free tier spins the service down when idle — this is normal
   and only affects the *first* request after a quiet period).
4. If it fails, the page will tell you to use the `.tex + Logo (.zip)` +
   Overleaf path instead — nothing is ever blocked.

### Notes on Render's free tier
- No credit card required to start, but this can change — check Render's
  current free-tier terms if signup asks for one.
- The free web service **sleeps after ~15 minutes of inactivity** and takes
  30–60 seconds to "wake up" on the next request. For a class project this
  is usually fine; if it bothers you or your class, upgrade the single
  service to a paid Starter plan (a few dollars/month) for an always-on
  backend.
- If Render's free tier policy has changed by the time you deploy, the same
  `Dockerfile` works unmodified on Railway, Fly.io, or any VPS — only the
  "create a service" steps differ.

---

## Running locally (for testing before you deploy)

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The server listens on `http://localhost:5000`. Test it with:
```bash
curl http://localhost:5000/health
```

To point `labweb.html` at your local server instead of the deployed one
while testing, open it as:
```
labweb.html?backend=http://localhost:5000
```

## Requirements on the host machine / container

- Python 3.9+
- A TeX Live installation with `pdflatex` on `PATH`, including these
  packages (all standard, included in most TeX Live installs):
  `geometry`, `graphicx`, `array`, `listings`, `xcolor`, `fancyhdr`,
  `titlesec`, `parskip`, `amsmath`, `enumitem`.

  On Debian/Ubuntu (this is exactly what the Dockerfile does):
  ```bash
  sudo apt-get update
  sudo apt-get install -y texlive-latex-base texlive-latex-recommended \
      texlive-latex-extra texlive-fonts-recommended
  ```

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` (local) / set by Render | Port the server listens on |
| `ALLOWED_ORIGINS` | `*` | CORS origin(s) allowed to call the API. Set this to your real frontend origin in production if you host `labweb.html` somewhere with a fixed URL |
| `MAX_CONTENT_LENGTH_MB` | `25` | Max request body size (LaTeX + images + logo) |
| `PDFLATEX_BIN` | `pdflatex` | Path to the pdflatex binary, if not on `PATH` |
| `COMPILE_TIMEOUT_SECONDS` | `40` | Per-pass timeout for the pdflatex subprocess |
| `COMPILE_PASSES` | `2` | Number of pdflatex passes (2 resolves page numbers correctly) |
| `FLASK_DEBUG` | `0` | Set to `1` for Flask's debug/auto-reload mode (dev only) |

Set these from Render's dashboard under your service → **Environment**, or
edit them directly in `render.yaml` before deploying.

## Architecture notes

- The compile sandbox is a fresh `tempfile`-based directory per request,
  cleaned up in a `finally` block so failed/crashed compiles don't leak
  files.
- Uploaded filenames are sanitized (`_safe_filename`) before being written
  to disk — no path traversal, no overwriting of unexpected files.
- `-no-shell-escape` is passed to `pdflatex` so the compiled document can't
  shell out, even though this generator's own template never needs that.
- Image/logo bytes are capped by `MAX_CONTENT_LENGTH_MB` and by a max image
  count, since this is a small lab-report tool, not a general file host.
- In production, `gunicorn` (not Flask's dev server) runs the app — this is
  already configured in the `Dockerfile`'s `CMD`.

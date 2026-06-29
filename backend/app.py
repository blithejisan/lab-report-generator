"""
GUB ADS Lab Report Generator - PDF Compile Backend
====================================================

A small Flask API that compiles LaTeX source (sent from labweb.html) into a
PDF using a real pdflatex installation, and returns the PDF bytes directly.

Endpoints:
    GET  /health    -> { "ok": true }                  (used by the frontend
                                                          to check availability)
    POST /compile    -> PDF binary on success, or
                        { "error": "...", "log": "..." } (HTTP 400) on failure

Run locally:
    pip install -r requirements.txt
    python app.py
    # Server listens on http://localhost:5000 by default

Deploying:
    Configure via environment variables (see Config section below) and run
    behind a production WSGI server, e.g.:
        gunicorn -w 2 -b 0.0.0.0:8000 app:app
    Set ALLOWED_ORIGINS to the real frontend origin(s) in production instead
    of "*".

Requirements on the host machine / container:
    - Python 3.9+
    - A working TeX Live installation with pdflatex on PATH, including the
      packages used by the generator: geometry, graphicx, array, listings,
      xcolor, fancyhdr, titlesec, parskip, amsmath, enumitem.
      (On Debian/Ubuntu: `apt-get install texlive texlive-latex-extra`)
"""

import os
import re
import base64
import shutil
import subprocess
import tempfile
import uuid

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# ----------------------------------------------------------------------------
# Config (env-var driven so this is deploy-ready without code changes)
# ----------------------------------------------------------------------------
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")
MAX_CONTENT_LENGTH_MB = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "25"))
PDFLATEX_BIN = os.environ.get("PDFLATEX_BIN", "pdflatex")
COMPILE_TIMEOUT_SECONDS = int(os.environ.get("COMPILE_TIMEOUT_SECONDS", "40"))
COMPILE_PASSES = int(os.environ.get("COMPILE_PASSES", "2"))  # 2 passes resolves
                                                              # page numbers/refs
MAX_IMAGE_COUNT = 30  # sanity cap; a lab report won't realistically exceed this

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_MB * 1024 * 1024
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# Allowed image extensions that may be written into the compile sandbox.
# Keeps this strictly to what the LaTeX template ever references.
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg"}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _safe_filename(name, fallback):
    """
    Returns a filename safe to place inside the compile sandbox: no path
    separators, no leading dots, restricted to a conservative character set.
    Falls back to a generated name if the input is empty or unsafe after
    stripping.
    """
    if not name:
        return fallback
    base = os.path.basename(name)
    base = re.sub(r"[^A-Za-z0-9_\-.]", "_", base)
    base = base.lstrip(".")
    if not base:
        return fallback
    return base


def _decode_data_or_base64(value):
    """
    Accepts either a raw base64 string or a data URL (data:image/png;base64,...)
    and returns the decoded bytes. Returns None if decoding fails.
    """
    if not value:
        return None
    if "," in value and value.strip().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None


def _write_files(workdir, tex_source, images, logo):
    """
    Writes the .tex source, any output images, and the logo file into workdir.
    `images` is a list of {"name": str, "data": base64-or-dataurl str}.
    `logo` is {"name": str, "data": base64-or-dataurl str} or None.
    Returns the path to the written .tex file.
    """
    tex_path = os.path.join(workdir, "report.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_source)

    if images:
        for i, img in enumerate(images[:MAX_IMAGE_COUNT]):
            name = _safe_filename(img.get("name"), f"output_q{i+1}.png")
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_IMAGE_EXT:
                continue
            data = _decode_data_or_base64(img.get("data"))
            if data is None:
                continue
            with open(os.path.join(workdir, name), "wb") as f:
                f.write(data)

    if logo and logo.get("data"):
        logo_name = _safe_filename(logo.get("name"), "ads_logo.png")
        ext = os.path.splitext(logo_name)[1].lower()
        if ext not in ALLOWED_IMAGE_EXT:
            logo_name = "ads_logo.png"
        data = _decode_data_or_base64(logo.get("data"))
        if data is not None:
            with open(os.path.join(workdir, logo_name), "wb") as f:
                f.write(data)
            # The LaTeX template always references "ads_logo.png" by name, so
            # make sure that exact file exists even if the upload had a
            # different extension/name.
            canonical = os.path.join(workdir, "ads_logo.png")
            if logo_name != "ads_logo.png" and not os.path.exists(canonical):
                shutil.copy(os.path.join(workdir, logo_name), canonical)

    return tex_path


def _run_pdflatex(workdir, tex_path):
    """
    Runs pdflatex against tex_path inside workdir, COMPILE_PASSES times.
    Returns (success: bool, log: str, pdf_path: str|None).
    """
    full_log = ""
    pdf_path = os.path.join(workdir, "report.pdf")

    for _ in range(max(1, COMPILE_PASSES)):
        try:
            proc = subprocess.run(
                [
                    PDFLATEX_BIN,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-no-shell-escape",
                    os.path.basename(tex_path),
                ],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return False, (
                "pdflatex was not found on the server. The administrator "
                "needs to install a TeX Live distribution (see backend "
                "README)."
            ), None
        except subprocess.TimeoutExpired:
            return False, (
                f"Compilation timed out after {COMPILE_TIMEOUT_SECONDS}s. "
                "The document may be too complex, or pdflatex is waiting on "
                "input (check for unescaped special characters)."
            ), None

        full_log += proc.stdout + proc.stderr
        if proc.returncode != 0:
            return False, full_log, None

    if not os.path.exists(pdf_path):
        return False, full_log + "\n[No PDF was produced.]", None

    return True, full_log, pdf_path


def _extract_useful_error(log):
    """
    pdflatex logs are long. Pull out the first '! ' error line plus a few
    lines of context so the frontend can show something actionable instead
    of a wall of text.
    """
    lines = log.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("!"):
            snippet = lines[i : i + 6]
            return "\n".join(snippet).strip()
    # Fall back to the tail of the log, which usually has the fatal reason.
    return "\n".join(lines[-15:]).strip()


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    pdflatex_available = shutil.which(PDFLATEX_BIN) is not None
    return jsonify({"ok": True, "pdflatex_available": pdflatex_available})


@app.route("/compile", methods=["POST"])
def compile_latex():
    payload = request.get_json(silent=True)
    if not payload or "tex" not in payload:
        return jsonify({"error": "Request must include a 'tex' field."}), 400

    tex_source = payload.get("tex") or ""
    images = payload.get("images") or []
    logo = payload.get("logo")

    if not tex_source.strip():
        return jsonify({"error": "Empty LaTeX source."}), 400
    if not isinstance(images, list):
        return jsonify({"error": "'images' must be a list."}), 400

    job_id = uuid.uuid4().hex[:12]
    workdir = os.path.join(tempfile.gettempdir(), f"labreport_{job_id}")
    os.makedirs(workdir, exist_ok=True)

    try:
        tex_path = _write_files(workdir, tex_source, images, logo)
        success, log, pdf_path = _run_pdflatex(workdir, tex_path)

        if not success:
            return (
                jsonify(
                    {
                        "error": "LaTeX compilation failed.",
                        "log": _extract_useful_error(log),
                        "full_log": log[-6000:],  # capped to keep payload sane
                    }
                ),
                400,
            )

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="lab_report.pdf",
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

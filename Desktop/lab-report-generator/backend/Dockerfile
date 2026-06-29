# Dockerfile for the Lab Report Generator PDF compile backend.
# This installs a full TeX Live distribution so pdflatex is available,
# then runs the Flask app behind gunicorn.

FROM python:3.11-slim

# Install TeX Live with the packages our LaTeX template actually uses
# (geometry, graphicx, array, listings, xcolor, fancyhdr, titlesec,
# parskip, amsmath, enumitem are all in texlive-latex-extra / -recommended).
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Render (and most platforms) inject PORT at runtime; default to 10000 for
# local `docker run` testing.
ENV PORT=10000
EXPOSE 10000

# Use gunicorn in production instead of Flask's dev server.
CMD gunicorn -w 2 -b 0.0.0.0:${PORT} --timeout 60 app:app

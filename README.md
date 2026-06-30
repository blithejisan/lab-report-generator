# 🧪 Lab Report Generator — GUB ADS

A web-based LaTeX lab report generator for Green University of Bangladesh (ADS Department) students. Fill in your details, paste your code and output screenshots, and get a properly formatted lab report — either as a ready-to-use `.tex` file (for Overleaf) or as a directly compiled PDF.

## 🔗 Live Links

- **Open the Generator:** https://blithejisan.github.io/lab-report-generator/labweb.html
- **Backend API (PDF compile service):** https://lab-report-backend-1vn7.onrender.com/health

## ✨ Features

- Fill in student name, ID, course info, university/department — all reusable for any student, nothing hardcoded
- Add multiple questions, each with its own code block and language (Python, R, C, C++, Java, JavaScript, SQL)
- Upload an output/result screenshot per question — automatically placed after the code in the report
- Upload a custom university logo, or use the built-in default
- **Generate PDF directly** — no need to manually use Overleaf
- Or **download the `.tex` + logo as a `.zip`** and compile it yourself on Overleaf
- Dynamic header and title page — always shows the current student's name, never hardcoded

## 🛠️ How It Works

This project has two parts:

1. **Frontend** (`labweb.html`) — a single-page app, hosted free via GitHub Pages. No installation needed; just open the link.
2. **Backend** (`backend/`) — a small Flask API that runs `pdflatex` to compile the LaTeX into a real PDF, hosted free on Render using Docker (with a full TeX Live install).

```
labweb.html          → the generator UI (GitHub Pages)
backend/
  app.py             → Flask API that compiles LaTeX to PDF
  Dockerfile          → installs TeX Live + runs the API (Render)
  requirements.txt
  README.md           → backend setup & deployment details
render.yaml            → Render Blueprint for one-click backend deploy
```

See [`backend/README.md`](backend/README.md) for backend setup, environment variables, and deployment instructions if you want to run or redeploy your own copy.

## ⚠️ Note on the Backend

The PDF-compile backend runs on Render's free tier, which spins down after ~15 minutes of inactivity. The **first** "Generate PDF" click after a quiet period may take 30–60 seconds while it wakes up — this is normal, not a bug. If it ever fails, the generator automatically falls back to letting you download the `.tex` + logo `.zip` to compile on Overleaf instead.

---

Built for GUB ADS students — feel free to fork and adapt for your own department or university.

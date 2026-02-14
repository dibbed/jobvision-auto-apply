# Changelog

## 2025-02-10

- Added JobVision auto-apply script: `jobvision_auto_apply.py`.
- Filter accepts only jobs with دورکاری (remote), گلستان (Golestan), or گرگان (Gorgan).
- Skip internship titles (کارآموز, Intern).
- Optional Gemini scoring; progress saved in `data/sent_jobs.json` and `data/applications.json`/`.csv`.
- Config in `config.py` and `.env.example`; debug HTML saved on errors.
- Added `--dry-run` and `--headless` CLI options.
- Added `.gitignore` for .env, logs, data, debug_html.

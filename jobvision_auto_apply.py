# -*- coding: utf-8 -*-
"""
JobVision Auto-Apply: automatically apply to recommended jobs that match
دورکاری (remote), گلستان (Golestan), or گرگان (Gorgan).
Uses Playwright for browser automation; optional Gemini for scoring.
"""

import argparse
import csv
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeout

import config

# --- Logging ---
LOG_FILE = config.LOGS_DIR / "jobvision_auto_apply.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class JobItem:
    """Single job card data from the recommended jobs list."""

    title: str
    company: str
    location: str
    job_url: str
    job_id: str
    raw_text: str = ""
    is_remote: bool = False
    is_golestan_or_gorgan: bool = False
    match_reason: str = ""


@dataclass
class ApplicationRecord:
    """One sent application record for applications.json/csv."""

    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    applied_at: str
    gemini_score: int = -1
    gemini_reason: str = ""


def load_sent_jobs() -> set[str]:
    """Load set of job IDs we have already applied to."""
    if not config.SENT_JOBS_FILE.exists():
        return set()
    try:
        data = json.loads(config.SENT_JOBS_FILE.read_text(encoding="utf-8"))
        return set(data.get("job_ids", []))
    except Exception as e:
        logger.warning("Could not load sent_jobs: %s", e)
        return set()


def save_sent_jobs(job_ids: set[str]) -> None:
    """Persist sent job IDs."""
    config.SENT_JOBS_FILE.write_text(
        json.dumps({"job_ids": list(job_ids), "updated": datetime.now().isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_applications() -> list[dict]:
    """Load existing applications list."""
    if not config.APPLICATIONS_JSON.exists():
        return []
    try:
        return json.loads(config.APPLICATIONS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not load applications: %s", e)
        return []


def append_application(record: ApplicationRecord) -> None:
    """Append one application and sync JSON + CSV."""
    apps = load_applications()
    apps.append(asdict(record))
    config.APPLICATIONS_JSON.write_text(json.dumps(apps, ensure_ascii=False, indent=2), encoding="utf-8")
    # CSV append
    write_csv_header = not config.APPLICATIONS_CSV.exists()
    with open(config.APPLICATIONS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["job_id", "title", "company", "location", "job_url", "applied_at", "gemini_score", "gemini_reason"])
        if write_csv_header:
            w.writeheader()
        w.writerow(asdict(record))


def extract_job_id_from_url(url: str) -> str:
    """Extract numeric job ID from JobVision URL e.g. /jobs/1307881/..."""
    m = re.search(r"/jobs/(\d+)", url or "")
    return m.group(1) if m else ""


def job_matches_location_filter(location_text: str, title: str) -> tuple[bool, str]:
    """
    Return (matches, reason). Accept only if location/title contains
    دورکاری، گلستان، or گرگان; skip کارآموز/Intern.
    """
    combined = (location_text or "") + " " + (title or "")
    combined_lower = combined.lower()
    if any(k in combined_lower for k in ("intern", "کارآموز")):
        return False, "skip: internship"
    for kw in config.ACCEPTED_LOCATION_KEYWORDS:
        if kw in (location_text or "") or kw in (title or ""):
            return True, f"accept: {kw}"
    # Also accept if "دورکاری" appears in raw text (e.g. in benefits)
    if "دورکاری" in combined:
        return True, "accept: دورکاری"
    return False, "skip: not in accepted locations (دورکاری، گلستان، گرگان)"


def collect_job_cards(page: Page) -> list[JobItem]:
    """
    From current recommended-jobs page, collect all job cards.
    Uses data from links and surrounding text for location/دورکاری.
    """
    items: list[JobItem] = []
    # Job links: a[href*='/jobs/']
    locator = page.locator('a[href*="/jobs/"]').filter(has_not=page.locator("img"))
    n = locator.count()
    for i in range(n):
        node = locator.nth(i)
        try:
            href = node.get_attribute("href") or ""
            if "/jobs/" not in href:
                continue
            title = node.inner_text().strip() or ""
            if not title or any(skip in title for skip in config.SKIP_TITLE_KEYWORDS):
                continue
            job_id = extract_job_id_from_url(href)
            if not job_id:
                continue
            full_url = href if href.startswith("http") else config.BASE_URL + href
            # Find parent card container to get company + location
            card = node.locator("xpath=ancestor::*[.//button[contains(., 'ارسال رزومه')]][1]").first
            if card.count() == 0:
                card = node.locator("xpath=ancestor::*[contains(@class, 'cursor-pointer') or name()='generic'][position()>=3][position()<=8]").first
            raw_text = ""
            company = ""
            location = ""
            if card.count() > 0:
                raw_text = card.inner_text() or ""
                # Simple heuristic: second line often company; line with city name is location
                lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
                for line in lines:
                    if line == title:
                        continue
                    if not company and len(line) < 80:
                        company = line
                        continue
                    if any(c in line for c in ["گرگان", "گلستان", "تهران", "مشهد", "دورکاری", "پاره وقت", "تمام وقت"]):
                        location = line
                    if "دورکاری" in line:
                        location = (location or "") + " " + line
            job_item = JobItem(
                title=title,
                company=company or "—",
                location=location or "—",
                job_url=full_url,
                job_id=job_id,
                raw_text=raw_text,
            )
            matches, reason = job_matches_location_filter(location + " " + raw_text, title)
            job_item.is_remote = "دورکاری" in (location + raw_text)
            job_item.is_golestan_or_gorgan = "گلستان" in (location + raw_text) or "گرگان" in (location + raw_text)
            job_item.match_reason = reason
            if matches:
                items.append(job_item)
        except Exception as e:
            logger.debug("Skip card %s: %s", i, e)
            continue
    return items


def get_apply_buttons(page: Page) -> list[tuple[str, any]]:
    """Get (job_id, button_handle) for each 'ارسال رزومه' in current list."""
    results = []
    buttons = page.get_by_role("button", name=re.compile("ارسال رزومه"))
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            card = btn.locator("xpath=ancestor::*[.//a[contains(@href,'/jobs/')]][1]").first
            if card.count() > 0:
                link = card.locator('a[href*="/jobs/"]').first
                href = link.get_attribute("href") or ""
                jid = extract_job_id_from_url(href)
                if jid:
                    results.append((jid, btn))
        except Exception:
            continue
    return results


def goto_with_retry(page: Page, url: str) -> bool:
    """Navigate with retries and timeout."""
    for attempt in range(1, config.GOTO_RETRIES + 1):
        try:
            page.goto(url, timeout=config.NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_timeout(min(1000, config.PAGE_LOAD_WAIT_MS))
            return True
        except PlaywrightTimeout as e:
            logger.warning("Goto attempt %s failed: %s", attempt, e)
            if attempt < config.GOTO_RETRIES:
                time.sleep(config.GOTO_RETRY_DELAY_SEC)
    return False


def check_logged_in(page: Page) -> bool:
    """Return True if we see logged-in menu (e.g. رزومه های ارسال شده) and no 'ورود | ثبت نام'."""
    try:
        if page.get_by_role("button", name=re.compile("ورود")).count() > 0:
            return False
        if page.locator("text=رزومه های ارسال شده").count() > 0 or page.locator("text=مشاغل پیشنهادی").count() > 0:
            return True
        return False
    except Exception:
        return False


def gemini_should_apply(title: str, company: str, location: str, raw_snippet: str) -> tuple[bool, int, str]:
    """
    Call Gemini to get apply (yes/no), score 0-100, and short reason.
    If GEMINI_API_KEY not set, returns (True, -1, "").
    """
    if not config.GEMINI_API_KEY:
        return True, -1, ""
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        prompt = f"""You are a job application filter. Given this job:
Title: {title}
Company: {company}
Location: {location}
Snippet: {raw_snippet[:500]}

Rules: Prefer دورکاری (remote), گلستان, گرگان. Reject only if clearly irrelevant (e.g. unrelated field).
Respond in JSON only: {{ "apply": true or false, "score": 0-100, "reason": "short reason in Persian or English" }}"""
        for attempt in range(1, config.GEMINI_RETRIES + 1):
            try:
                resp = model.generate_content(prompt)
                text = (resp.text or "").strip()
                # Extract JSON
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    obj = json.loads(text[start:end])
                    apply = bool(obj.get("apply", True))
                    score = int(obj.get("score", 50))
                    reason = str(obj.get("reason", ""))[:200]
                    return apply and score >= config.GEMINI_APPLY_THRESHOLD, score, reason
            except Exception as e:
                logger.debug("Gemini attempt %s: %s", attempt, e)
                if attempt < config.GEMINI_RETRIES:
                    time.sleep(config.GEMINI_RETRY_DELAY_SEC)
        return True, -1, "gemini_error"
    except ImportError:
        logger.warning("google-generativeai not installed; skipping Gemini.")
        return True, -1, ""


def save_page_html_for_debug(page: Page, prefix: str = "error") -> None:
    """Save current page HTML for debugging."""
    try:
        path = config.DEBUG_HTML_DIR / f"{prefix}_{int(time.time())}.html"
        path.write_text(page.content(), encoding="utf-8")
        logger.info("Saved debug HTML: %s", path)
    except Exception as e:
        logger.warning("Could not save debug HTML: %s", e)


def run(dry_run: bool = False, headless: bool = True) -> None:
    """Main run: open browser, ensure login, iterate recommended jobs, apply with filters."""
    sent = load_sent_jobs()
    applied_this_run = 0
    skipped_filter = 0
    skipped_already = 0
    errors = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale="fa-IR", viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.set_default_timeout(config.DEFAULT_TIMEOUT_MS)

        try:
            if not goto_with_retry(page, config.BASE_URL):
                logger.error("Failed to open base URL")
                save_page_html_for_debug(page, "goto_fail")
                return
            if not check_logged_in(page):
                logger.warning("Not logged in. Please log in in the browser window and press Enter here when done.")
                if not headless:
                    input()
                else:
                    logger.error("Cannot wait for login in headless mode. Run without --headless to log in.")
                    return
            if not goto_with_retry(page, config.RECOMMENDED_JOBS_URL):
                logger.error("Failed to open recommended jobs")
                save_page_html_for_debug(page, "recommended_fail")
                return

            for page_num in range(1, config.MAX_PAGES + 1):
                page.wait_for_timeout(config.PAGE_LOAD_WAIT_MS)
                cards = collect_job_cards(page)
                buttons_by_id = {jid: btn for jid, btn in get_apply_buttons(page)}

                for job in cards:
                    if job.job_id in sent:
                        skipped_already += 1
                        continue
                    if "skip:" in job.match_reason:
                        skipped_filter += 1
                        continue
                    # Optional Gemini
                    do_apply, score, reason = gemini_should_apply(
                        job.title, job.company, job.location, job.raw_text[:600]
                    )
                    if not do_apply:
                        skipped_filter += 1
                        logger.info("Gemini skip: %s | %s | %s", job.title, score, reason)
                        continue
                    btn = buttons_by_id.get(job.job_id)
                    if not btn:
                        continue
                    if dry_run:
                        logger.info("[DRY-RUN] Would apply: %s | %s | %s", job.title, job.company, job.location)
                        applied_this_run += 1
                        sent.add(job.job_id)
                        append_application(
                            ApplicationRecord(
                                job_id=job.job_id,
                                title=job.title,
                                company=job.company,
                                location=job.location,
                                job_url=job.job_url,
                                applied_at=datetime.now().isoformat(),
                                gemini_score=score,
                                gemini_reason=reason,
                            )
                        )
                        continue
                    try:
                        btn.click()
                        page.wait_for_timeout(1500)
                        sent.add(job.job_id)
                        append_application(
                            ApplicationRecord(
                                job_id=job.job_id,
                                title=job.title,
                                company=job.company,
                                location=job.location,
                                job_url=job.job_url,
                                applied_at=datetime.now().isoformat(),
                                gemini_score=score,
                                gemini_reason=reason,
                            )
                        )
                        applied_this_run += 1
                        logger.info("Applied: %s | %s", job.title, job.company)
                    except Exception as e:
                        errors += 1
                        logger.exception("Error applying to %s: %s", job.job_id, e)
                        save_page_html_for_debug(page, "apply_error")

                save_sent_jobs(sent)
                # Next page: pagination has listitem with links "1", "2", "3", "آخرین"
                next_page_num = page_num + 1
                next_link = page.locator("listitem >> a").nth(next_page_num - 1)
                if next_link.count() == 0:
                    break
                try:
                    next_link.click()
                except Exception:
                    break

        except Exception as e:
            logger.exception("Run error: %s", e)
            save_page_html_for_debug(page, "run_error")
        finally:
            browser.close()

    # Summary
    logger.info(
        "Summary: applied=%s, skipped_filter=%s, skipped_already=%s, errors=%s",
        applied_this_run, skipped_filter, skipped_already, errors,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="JobVision Auto-Apply (دورکاری، گلستان، گرگان)")
    parser.add_argument("--dry-run", action="store_true", help="Do not click apply; only log and record")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser headless")
    args = parser.parse_args()
    run(dry_run=args.dry_run, headless=args.headless)


if __name__ == "__main__":
    main()

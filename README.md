# JobVision Auto-Apply

اتوماسیون ارسال رزومه به **مشاغل پیشنهادی** جاب‌ویژن با فیلتر **دورکاری، گلستان و گرگان**.

## پیش‌نیاز

- Python 3.11+
- مرورگر (برای Playwright)

## نصب

```bash
pip install -r requirements.txt
playwright install chromium
```

کپی `.env.example` به `.env` و در صورت تمایل `GEMINI_API_KEY` را پر کنید (اختیاری).

## فیلترها

- **قبول:** آگهی‌هایی که در محل کار یا توضیحات شامل **دورکاری**، **گلستان** یا **گرگان** باشند.
- **حذف:** عنوان‌های **کارآموز** / Intern.

## اجرا

1. **اول لاگین کنید:** یک بار بدون `--headless` اجرا کنید تا در مرورگر به جاب‌ویژن لاگین کنید و وقتی آماده شد Enter بزنید:

```bash
python jobvision_auto_apply.py
```

2. **حالت خشک (بدون کلیک واقعی):**

```bash
python jobvision_auto_apply.py --dry-run
```

3. **با مرورگر پنهان (بعد از لاگین):**

```bash
python jobvision_auto_apply.py --headless
```

## خروجی‌ها

- `logs/jobvision_auto_apply.log` — لاگ اجرا
- `data/sent_jobs.json` — شناسه آگهی‌های ارسال‌شده
- `data/applications.json` و `data/applications.csv` — لیست درخواست‌ها
- در خطا: `debug_html/` — یک کپی HTML صفحه برای دیباگ

## تنظیمات

ثابت‌ها در `config.py` (مثلاً تعداد صفحه، تایم‌اوت، آستانه امتیاز Gemini).

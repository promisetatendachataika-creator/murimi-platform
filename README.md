# Murimi Intelligent Hub

**One trusted place where every party in a farming deal is checked, and the deal is tracked from funding to harvest to delivery.**

Murimi connects **farmers, landowners, investors and transport drivers** in Zimbabwe. Each person gets a verified account and their own dashboard, and field officers check people and land before deals go ahead.

## Features

- **Four user roles:** farmers, landowners, investors and drivers, each with their own sign-up questions and dashboard
- **Verification:** field officers verify people and land; each user sees their status and a "Next steps" checklist
- **Private documents:** IDs, title deeds and farm photos are uploaded to private storage and reviewed by staff
- **Farm projects:** funding targets and milestones; investors register interest
- **Market prices:** staff post crop prices by market in US$ and ZiG; farmers see prices for their crops
- **Haulage jobs:** transport jobs matched to drivers' truck sizes
- **WhatsApp codes:** phone verification and password reset through the WhatsApp Cloud API
- **Staff admin panel:** Django admin for managing users, documents, prices and jobs

## Tech stack

| Layer | Technology |
| --- | --- |
| Back end | Python 3, Django 5.2 |
| API | 21 JSON endpoints under `/api/` |
| Database | SQLite (development), PostgreSQL (production) |
| Front end | Single-page app in HTML, CSS and JavaScript |
| Animation | Three.js, Lottie |
| Messaging | WhatsApp Cloud API (Meta) |
| Security | Session authentication, CSRF protection, rate limiting |
| Testing | Django test runner (40 tests), Playwright |

## Project structure

```
murimi-platform/
├─ murimi/      Project settings and URL map
├─ accounts/    Sign-up, login, profiles, checklist, WhatsApp codes
├─ projects/    Farm projects and investor interest
├─ documents/   Private uploads and staff review
├─ market/      Market prices and haulage jobs
└─ web/         Serves the single-page front end
```

## Getting started

```bash
# 1. Clone the repository
git clone https://github.com/promisetatendachataika-creator/murimi-platform.git
cd murimi-platform

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the database and run
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open **http://127.0.0.1:8000**. The staff admin is at **/admin/**.
On Windows you can also double-click `start-windows.bat`.

## Running tests

```bash
python manage.py test accounts projects documents market
```

## Roadmap

- [x] Accounts, verification, documents, farm projects, market prices, haulage jobs
- [ ] Deploy to production with PostgreSQL and HTTPS
- [ ] Organisation workspaces for companies and co-operatives
- [ ] Escrow payments with a licensed partner

## Author

**Promise Chataika**, BSc Computer Science, University of Zimbabwe
[LinkedIn](https://www.linkedin.com/in/promise-chataika-03178a335) | [Portfolio](https://promisechataika.netlify.app)

The live server reads its secrets from environment variables; see `.env.example` for the list. On your own laptop none are needed.

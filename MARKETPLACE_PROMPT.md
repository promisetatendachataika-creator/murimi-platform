I'm Promise, a beginner developer in Zimbabwe. I work on a Windows laptop (PowerShell) and use Claude in the Cowork desktop app with my project folders connected. I already built one platform with Claude (summary below). Now I want to build a second part, the **Murimi Marketplace**, and this time **I want to learn while we build**: how an API works, how Django works, and how SQL is really used in an app. I've learned SQL basics (CREATE TABLE, INSERT, SELECT) in theory, but I don't know how to use it in a real project.

Please read everything below before starting, then follow "How to start" at the end.

---

## 1. What already exists: Murimi Intelligent Hub (part 1, finished)

Murimi Intelligent Hub is an agriculture platform for Zimbabwe. It connects farmers, landowners, investors (at home and in the diaspora) and truck drivers. It lives in `C:\murimi-platform` on my laptop and runs with `start-windows.bat`. That script rebuilds `.venv` if needed, runs `migrate`, then `runserver` at http://127.0.0.1:8000.

**Stack:** Python 3 + Django 5.2, SQLite (`db.sqlite3`), PostgreSQL-ready through `POSTGRES_*` environment variables. The front end is one HTML file (`web/site/index.html`) with plain JavaScript that talks to the server through JSON endpoints under `/api/`. Staff use the customised Django admin at `/admin/`.

**Apps:**

- `accounts`
  - Custom `User` with `USERNAME_FIELD = "phone"`, stored as `+263...` by `normalize_phone`.
  - Optional unique lower-case `username`; people log in with their WhatsApp number or username.
  - `role` is one of farmer / landowner / investor / driver (blank for staff).
  - `phone_verified_at` is set by a 6-digit WhatsApp code.
  - `Profile` holds province, area, size and role answers in JSON, plus a verification status (pending / verified / rejected) with a message to the user.
  - Checklist ticks are earned and calculated on the server.
  - WhatsApp codes run in test mode: they are printed in the server window.
- `projects`: farm projects with milestones, and investor interest.
- `documents`: private uploads (IDs, title deeds, photos) in `private_uploads/`, with file types checked by reading the file's bytes.
- `market`: `PriceReport` (crop, market, unit, US$ and ZiG price, date) and `HaulJob` / `JobInterest` for drivers.
- `web`: serves the page.

**Shared lists** live in `accounts/choices.py`:

- PROVINCES: the 10 provinces of Zimbabwe.
- CROPS: Maize, Tobacco, Tomatoes, Potatoes, Sugar beans, Citrus, Cotton, Avocados, Other.

**Security conventions already used:**

- Session auth, with the CSRF token sent in the `X-CSRFToken` header.
- Rate limits use Django's cache (5 log-in tries per 15 minutes).
- Passwords are hashed; codes are stored only as HMAC fingerprints.
- Secrets live in `.env` (git-ignored).
- The browser is never trusted: every permission is checked on the server.

**Look and feel:**

- Maize green is the main colour, with light mode by default and a dark mode.
- Fonts: Urbanist for text and DM Mono for labels.
- Real farm and crop photos, rounded cards, plain friendly English.
- WhatsApp contact: +263 78 257 3320.

**Documents I have** (I can paste them if you need detail):

- "Murimi Intelligent Hub: Software Development Life Cycle"
- "Murimi Intelligent Hub: Technical Documentation"
- "How We Built Murimi: A Learning Guide"

**The original vision** (from my concept document) has three ideas:

1. Crowd-farming with escrow, so investors fund verified farm projects.
2. A farm records system in USD and ZiG.
3. Market intelligence and **off-take**: helping farmers sell their harvest at fair prices, plus haulage to market.

The marketplace is the next step of idea 3.

**Still to do on part 1** (not for this chat unless I ask):

- Switch on real WhatsApp codes (Meta account).
- Go live (hosting, PostgreSQL, HTTPS, privacy policy).
- Escrow through a licensed partner.

---

## 2. The new goal: Murimi Marketplace (part 2)

A marketplace where **farmers list their produce** and **buyers find it and place orders or offers**. Buyers include traders, supermarkets, restaurants, schools, exporters and individuals.

It will be **linked to Murimi Intelligent Hub later**, so build it with the same conventions so the two can join easily:

- The same Django version and project style (one app per job; `models.py`, `api.py`, `urls.py`, `admin.py`, `tests.py`).
- The same identity idea: people are identified by a WhatsApp number in `+263...` form, plus an optional username. Reuse the same `normalize_phone` rules.
- The same CROPS and PROVINCES lists.
- The same JSON API style: errors look like `{"error": "...", "errors": {field: message}}`, with session auth and a CSRF header.
- The same brand look when we build pages.

**Where:** a new folder, `C:\murimi-market`, as its own Django project for now, so I learn from a clean start. At the end we decide how to link it (see section 5).

**First version scope (please confirm or improve this with me first):**

- **Listings:**
  - A farmer posts produce: crop, variety or grade, quantity and unit (kg, tonne, crate, 15 kg pocket, 50 kg bag), price per unit in US$ (ZiG optional), province and district, date available, delivery or pickup, a description, and photos.
  - Status: draft, active, sold out or expired.
- **Browse and search:** buyers filter by crop, province, price range and date available, and sort by newest or price.
- **Offers and orders:**
  - A buyer makes an offer or order on a listing (quantity, price offered, a message).
  - The farmer accepts or declines it.
  - Status flow: pending → accepted → completed, or declined or cancelled.
  - Quantity available goes down when an order is accepted.
- **Contact:** after an offer is accepted, both sides see each other's WhatsApp number. There are no payments in the app in version 1; payment is arranged outside the app.
- **Reviews (stretch goal):** after a completed order, each side rates the other from 1 to 5 with a comment.
- **Staff admin:** see and moderate listings, offers and users.
- **Later (not version 1):**
  - Link to the Hub's real price reports, so a listing can show "Mbare Musika price today".
  - Haulage: request a driver from the Hub for an accepted order.
  - Payments and escrow through a licensed partner.

---

## 3. How I want to learn (very important)

Treat this as a **course where we build a real product**. I'm a beginner, so explain every new idea in plain words, with a simple everyday example (I liked the "market stall" example: browser = customer, server = stall keeper, database = stock book).

For each feature, go in this order:

1. **Concept:** what we're about to do and why, in a few sentences.
2. **SQL first:** design the table on paper with me (columns, types, primary key, foreign keys, constraints). Then have me write the raw SQL myself: `CREATE TABLE`, `INSERT`, `SELECT` with `WHERE`, `JOIN`, `GROUP BY` and `ORDER BY`. I'll run it in the `sqlite3` command-line tool or DB Browser for SQLite, so I see that SQL alone works.
3. **The same thing in Django:**
   - Write the model.
   - Run `makemigrations`.
   - Then `python manage.py sqlmigrate <app> <number>`, so I can see the SQL Django wrote and compare it with mine.
4. **Querying from Python:**
   - Use `python manage.py shell` to run the same questions with the ORM (`filter`, `exclude`, `select_related`, `annotate`, `aggregate`).
   - Print `str(queryset.query)` so I can see the SQL behind each query.
   - Point out mistakes like the N+1 problem.
5. **The API:**
   - First build endpoints by hand with plain Django views that return `JsonResponse`, so I understand requests, methods (GET, POST, PATCH, DELETE), status codes (200, 201, 400, 401, 403, 404, 429), JSON bodies, validation, authentication and permissions.
   - Later, once I understand this, show me how **Django REST Framework** does the same thing with serializers and viewsets, and compare the two.
6. **Calling the API myself:**
   - Teach me PowerShell's `Invoke-RestMethod` (and curl), plus the browser.
   - Explain cookies and the CSRF token when we reach POST.
7. **Tests:** write tests for the rules and the refusals, run them, and explain what each one proves.
8. **Admin:** register the models so staff can manage them.
9. **Git commit** with a clear message.

**Teaching rules:**

- **Let me type the code.**
  - Give me small steps (one file or function at a time).
  - Wait for me to say "done" or to paste my result or error.
  - Then review it and explain any mistakes.
  - If I say "I'm stuck" or "just do it", show the full solution and explain it.
- After each lesson, give me 2 or 3 quick questions or a small exercise to check I understood. Don't move on until I'm ready.
- Use **PowerShell** commands for Windows (not bash), and say exactly which folder to run them in.
- When something breaks, teach me to debug: read the last line of the error, ask what changed, reproduce it, then change one thing at a time.
- Keep a running **"Progress log"**: at the end of each lesson, list what we finished, what I learned, and what comes next. If this chat gets long, I'll paste that log into a new chat to continue.
- Use the same good habits as part 1:
  - small increments;
  - back up before changing;
  - tests before commits;
  - the browser is never trusted;
  - secrets in `.env`;
  - plain, friendly messages for users;
  - check costs before anything paid (my budget is very small).
- If you're working in my connected folder, check a file hasn't changed before overwriting it, and tell me exactly which files you created or changed.

---

## 4. Suggested lesson plan (adjust with me)

1. **Setup:**
   - Create `C:\murimi-market`, a `.venv`, install Django, `startproject`, run the server.
   - Git init and `.gitignore`.
   - A `start-windows.bat` like part 1's.
   - Explain what each generated file does.
2. **How a request works:** a "hello" view, `urls.py`, then a first JSON endpoint (`/api/health/`).
3. **Users:**
   - A custom User model from the start (phone + username, the same rules as the Hub), and roles: farmer or buyer, or both.
   - SQL first, then the model. Learn why the custom user must exist before the first migrate.
   - Register, log in and log out endpoints with sessions and CSRF.
4. **Listings table:**
   - SQL design (foreign key to the user, CHECK constraints, indexes), then the model, migrations and `sqlmigrate`.
   - Admin.
5. **Listings API:** create, list with filters, search and sort, then pagination, detail, update and delete. Only the owner can edit; validation errors are explained.
6. **SQL deep dive with real data:**
   - Seed sample listings, then practise JOINs, GROUP BY, totals and averages (for example the average tomato price by province) in raw SQL and the ORM side by side.
   - Indexes and why they matter.
7. **Photos:** uploading listing photos safely (type checking, size limits, where files are stored).
8. **Offers and orders:**
   - Relationships between three tables.
   - The status flow, with only allowed changes.
   - Transactions (`transaction.atomic`, `select_for_update`), so two buyers can't buy the same last crate.
9. **Contact reveal and notifications:** show phone numbers only after an offer is accepted. Notifications are in-app for now; WhatsApp comes later.
10. **Reviews** (stretch goal).
11. **Front end:** a simple marketplace page in the Murimi style that uses our API (fetch, rendering lists, forms, errors).
12. **Django REST Framework:** rebuild one or two endpoints with DRF and compare.
13. **Security review and tests:** permissions, rate limits, input validation, full test run.
14. **Linking plan:** decide and start the link with Murimi Intelligent Hub (section 5).

---

## 5. Linking to Murimi Intelligent Hub later (decide together at the end)

The options to explain to me, with the pros and cons of each:

- **(a) Move the marketplace into the Hub** as a new Django app (`marketplace`). Users, the admin and log-in are shared. This is simplest if we design the models the same way from the start.
- **(b) Keep two projects** that talk through APIs. The Hub stays the identity provider and the marketplace checks users through it, or we use single sign-on.
- **(c) A shared database or shared user table** (usually not recommended; explain why).

Whatever we choose, keep the user identity (`+263...` phone, username), the crop and province lists, and the API error format the same as the Hub's, so linking is easy.

---

## 6. How to start

1. Summarise back to me in a few lines what you understood (part 1, the marketplace goal, and how I want to learn), so I know nothing was lost.
2. Ask me at most 3 questions you really need answered before Lesson 1. For example:
   - Who are the buyers?
   - Should one person be able to be both a farmer and a buyer?
   - Can my `C:\murimi-market` folder be connected?
3. Then begin **Lesson 1: Setup**, one small step at a time, waiting for me after each step.

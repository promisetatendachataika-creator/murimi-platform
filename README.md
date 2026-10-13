# Murimi Intelligent Hub · Platform

The Murimi website plus the server behind it: accounts with passwords, sign-up
for the four kinds of user, everyone's own dashboard ("My spot"), and a staff
admin where the team sees and verifies every sign-up.

## What's in here

| Folder / file | What it does |
|---|---|
| `web/site/index.html` | The whole website (landing page, sign-up, log in, dashboards) |
| `accounts/` | Accounts, log in, sign-up checks and the API the website calls |
| `accounts/choices.py` | The provinces, crops and options people can pick |
| `accounts/admin.py` | The staff admin screens |
| `accounts/tests.py` | Automatic checks for sign-up, log in, passwords and limits |
| `murimi/settings.py` | Settings (reads secrets from environment variables) |
| `start-windows.bat` | Double-click to run everything on a Windows PC |

## Run it on your computer (Windows)

1. Install **Python 3.12 or newer** from python.org. On the first installer
   screen, tick **"Add python.exe to PATH"**.
2. Unzip this folder somewhere, for example `Documents\murimi-platform`.
3. Double-click **`start-windows.bat`**. The first run takes a minute while it
   installs Django.
4. Open **http://127.0.0.1:8000** in your browser. Sign up as a farmer,
   landowner, investor or driver.

### Create your staff login (once)

Open Command Prompt in the folder and run:

```
.venv\Scripts\activate
python manage.py createsuperuser
```

It asks for a WhatsApp number (this is your login) and a password. Then go to
**http://127.0.0.1:8000/admin**. You can:

- see every sign-up, newest first
- filter by role (farmer, landowner, investor, driver), province or check status
- open a person to see all their answers and add private staff notes
- select people and choose **"Mark selected people as verified"**
- reset someone's password if they forget it

### Run the automatic checks

```
.venv\Scripts\activate
python manage.py test accounts projects documents market
```

All 40 should pass.

## How accounts work

- People log in with their **WhatsApp number and a password**. Email is optional,
  because many farmers don't use email.
- Numbers are stored in one standard form, so `0771234567`,
  `077 123 4567` and `+263 77 123 4567` are the same account.
- Passwords are stored hashed (never readable), must be 8+ characters, and can't
  be a common password, all numbers, or too similar to the person's name or number.
- After 5 wrong passwords for one number, log in is blocked for 15 minutes.
- Sessions last 30 days. Every form is protected against cross-site request forgery.

## WhatsApp codes (confirm number, forgot password)

People confirm their WhatsApp number with a 6-digit code from their own space,
and use **Forgot password?** on the log-in page to set a new password with a code.

- A code works for 10 minutes and only once. 5 wrong tries and it stops working.
  People wait 60 seconds between codes, and get at most 5 codes an hour.
- Codes are never stored, only a fingerprint of them. **Admin → Phone codes**
  shows when codes were sent and used. **Users** shows who has confirmed.
- If someone changes their number, they have to confirm the new one.

### Test mode (the default, free)

Nothing is sent. The code is printed in the black server window, and on your
own computer the website also shows it in a yellow "Test mode" box.

### Sending real WhatsApp messages

1. Create a Meta Business account and a WhatsApp app at developers.facebook.com
   (WhatsApp → Getting started). Add a bank card under billing. Each code costs
   about US$0.005 in Zimbabwe.
2. Create a message template: category **Authentication**, name `murimi_code`,
   language English, with the "Copy code" button. Wait for it to be approved.
3. Make a file called `.env` next to `manage.py` (it is never uploaded to GitHub):

   ```
   MURIMI_CODE_SENDER=whatsapp
   WHATSAPP_TOKEN=paste-your-permanent-access-token
   WHATSAPP_PHONE_NUMBER_ID=paste-the-phone-number-id
   ```

4. Restart `start-windows.bat`. To go back to test mode, change the first line to
   `MURIMI_CODE_SENDER=console` (or delete the file).

## Uploaded documents (IDs, title deeds, photos)

People upload these from their own space. They are saved in the `private_uploads`
folder, which is **not** part of the public website: a file can only be opened
by its owner or by Murimi staff (through `/api/documents/<id>/file/`).

- Staff review them under **Documents** in the admin, or at the bottom of each
  person's page under **Users**. Set **Accepted** or **Needs redoing**, and write a
  note the person will see.
- **Back up `private_uploads` together with `db.sqlite3`.** One without the other
  is incomplete.
- `private_uploads` is in `.gitignore`, so people's IDs never go to GitHub.
- On the live server, keep this folder on a disk that survives restarts (or a
  private cloud storage bucket) and set `MURIMI_UPLOADS_DIR` to its path.

## Before going live

1. **Hosting.** Any host that runs Python works (for example Render, Railway,
   a VPS, or a South African cloud region for lower latency).
2. **Database.** Switch from the built-in SQLite file to PostgreSQL: set the
   `POSTGRES_*` variables from `.env.example` and add `psycopg[binary]` to
   `requirements.txt`.
3. **Secrets.** Set `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`,
   and your domain in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.
4. **HTTPS.** Required. The settings switch on secure cookies and HTTPS
   redirects automatically when `DJANGO_DEBUG=False`.
5. **Login limits.** With more than one server process, move the cache to Redis
   so the 5-attempt limit is shared between them.
6. Run `python manage.py check --deploy`. It should report nothing except the
   optional HSTS preload notice.

## What to build next

1. **Switch WhatsApp codes on** (see above) once the Meta account is ready.
2. **Going live**: hosting, PostgreSQL, HTTPS and a privacy policy.
3. **Escrow and payments.** Only through a licensed bank or payment provider,
   after legal advice.

## Keeping the website and server in step

The options in `accounts/choices.py` must match the `ROLES` lists in
`web/site/index.html`. If you add a crop or province, add it in both places.

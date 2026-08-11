# Phase 5 Setup — AU Deal Hunter

## 1. Supabase project
Create a Supabase project. In SQL Editor run `supabase/schema.sql`.

## 2. Create the secret admin login
Supabase Dashboard → Authentication → Users → Add user.
Use an internal synthetic email in this form:
`YOUR_SECRET_USERNAME@au-deal-hunter.local`
and set a strong password.

Copy that user's UUID. In SQL Editor run:
```sql
insert into public.admin_users(user_id, username)
values ('PASTE-USER-UUID', 'YOUR_SECRET_USERNAME');
```
Only a user present in `admin_users` is authorised by RLS.

## 3. Configure the browser safely
Supabase → Project Settings/API. Put only the project URL and **publishable** key in `docs/config.js`.
Never put a secret/service-role key in `docs/`.

## 4. Add GitHub Actions secrets
Repository → Settings → Secrets and variables → Actions:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` (or use service-role legacy key only if your project uses that model)
- `DISCORD_WEBHOOK_URL`
- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`
- Amazon Creators credentials when your Amazon AU Associates/Creators API account is approved.

## 5. Admin URL
Your Pages URL + `/admin.html`
Example: `https://USERNAME.github.io/au-deal-hunter/admin.html`

## 6. Australia enforcement
Phase 5 rejects explicit non-AUD records and records market=`AU`, currency=`AUD`. eBay uses `X-EBAY-C-MARKETPLACE-ID: EBAY_AU`.

## 7. Important
The username is converted internally to `username@au-deal-hunter.local` for Supabase password authentication. The username is not itself a security boundary; the password, Supabase Auth controls, and RLS are what protect the admin area.

# Tree Plantation Social Tracker

A Django platform for tree-planting communities and commercial farms. The home page introduces both audiences; community posts live at `/community/`, while Grove provides organization workspaces.

## Features

- **User Registration & Authentication**
  - Register, log in, and log out securely
  - Edit profile (username, email, password, profile picture)

- **Social Feed**
  - Public community feed shows all tree posts from all users
  - Each post displays:
    - User avatar and name
    - Tree name, species, image, location, status, and last update
    - Reaction counts (👍 Like, ❤️ Love, 😮 Wow, 😢 Sad)
    - Comments with user info and timestamps
    - "Details" button to view full post
    - Delete button (only for the post owner)

- **Impact Reactions**
  - Five intent-based reactions with three commitment levels and optional notes
  - Planting pledges, practical help offers, notifications, and weighted impact scores
  - Context-aware reaction ordering and a latest-reactions timeline
- **Social Interactions**
  - React without reloading the feed and add comments with HTMX
  - Only logged-in users can react, comment, or add trees
- **Community Core**
  - Email-based signup, onboarding, login with remember-me, and password reset
  - Public gardener profiles, follow/unfollow, follower lists, discovery, and notifications
  - Mobile bottom navigation and installable PWA shell with a public-page offline fallback
  - English/Bengali language middleware and Bengali font support
- **Engagement tools**
  - Achievement badges, post/login/reaction streaks, a monthly streak freeze, and leaderboards
  - Daily and weekly garden challenges, scheduled posts, and in-app streak/comeback reminders
  - Multi-image and short-video tree posts, drafts, hashtags, search, species/location discovery, and garden insights

- **Tree Management**
  - Add new trees with images and structured location
  - Identify species from an uploaded image with PlantNet and iNaturalist fallback
  - Request a cached, image-based AI health analysis with confidence and care recommendations
  - Edit or delete your own tree posts
  - View detailed information for each tree

- **Profile Management**
  - Upload/change profile picture (avatar)
  - Edit username and email
  - Change password with confirmation
  - Personal or Business/Farm account type

- **Grove farm workspace**
  - Organization workspaces with owner, manager, worker, and viewer roles
  - Map-drawn plots with street and satellite basemaps
  - CSV tree-batch registration and public QR-linked batch records
  - Plot tasks, worker assignments, optional completion photos, and plot health records
  - Plot-level Gemini image health analysis when configured
  - BDT financial ledger with PDF export
  - Certification document vault with member-checked downloads
  - Carbon screening estimates and a sell/buy/hire marketplace scaffold
  - Public farm profiles and a dual-audience animated landing page

- **Modern UI/UX**
  - Responsive, card-based feed with Tailwind CSS, Alpine.js, and HTMX
  - Light/dark themes follow system preference and can be overridden manually
  - User avatars (uploaded or auto-generated)
  - All posts visible to everyone; social actions require login

## Getting Started

1. **Clone the repository**
2. **Install dependencies** (in your virtual environment):
   ```bash
   python -m pip install -r requirements.txt
   npm install
   npm run build:css
   ```
3. **Apply migrations:**
   ```bash
   python manage.py migrate
   ```
4. **Run the development server:**
   ```bash
   python manage.py runserver
   ```
5. **Visit** [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.

To run the PostgreSQL-backed container stack, copy `.env.example` to `.env`,
replace both placeholder secrets, and run `docker compose up --build`. The web
container applies migrations before serving the application. Local development
continues to use SQLite unless `DB_NAME` is configured.

Species identification uses `PLANTNET_API_KEY` when configured, then falls back
to iNaturalist. Health analysis uses Gemini Vision and requires `GEMINI_API_KEY`.
Both features return explicit errors when their providers are unavailable, and
health results are cached by the tree image. AI health scores are informational,
not a substitute for professional tree-care advice.

The community signup, profile, follow, notification, and PWA flows are available
alongside the existing legacy registration route. Password reset email uses
Django's configured email backend; configure a real backend before production.
The service worker only stores explicitly marked anonymous community/profile
pages and static assets; signed-in pages are not placed in its offline cache.
Google OAuth, bot protection, web-push delivery, translated message catalogs,
and physical iOS/Android device testing are not configured yet.

## Vercel deployment

The Django app has a Vercel Python entry point and daily engagement cron, but
deployment requires managed services because Vercel functions do not provide
persistent local database or upload storage:

1. Create a managed PostgreSQL database and an S3-compatible object bucket
   (for example, Cloudflare R2). Keep the bucket private; file links use signed
   URLs.
2. Configure Vercel environment variables: `DJANGO_SECRET_KEY`,
   `DATABASE_URL` (PostgreSQL URL with TLS), `AWS_STORAGE_BUCKET_NAME`,
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`,
   `AWS_S3_REGION_NAME` (usually `auto` for R2), `CRON_SECRET`,
   `GEMINI_API_KEY` (optional; curated challenges are used when absent), and
   `PLANTNET_API_KEY` (optional). Add any production Vercel origin to
   `CSRF_TRUSTED_ORIGINS` when your deployment needs it. Production redirects
   to HTTPS and starts with a one-hour HSTS policy; increase
   `SECURE_HSTS_SECONDS` only after verifying all intended domains use HTTPS.
3. Before the first deployment, point a trusted local environment at the
   managed database and run `python manage.py migrate`. Import any existing
   SQLite records and copy media files to the bucket separately; deployment
   does not automatically migrate local data.
4. Deploy the repository through Vercel. The Python function serves Django
   and WhiteNoise serves collected static files. The daily cron runs at
   00:00 UTC (06:00 Bangladesh time) to publish scheduled posts, create the
   next AI-or-curated challenge, and queue in-app reminders.

The Vercel setup does not configure transactional email or external data
imports. Verify database backups, bucket access policies, provider credentials,
and the cron response in Vercel logs before inviting users.

Grove map boundaries use Leaflet, OpenStreetMap, and Esri World Imagery tiles.
Map tile providers are external services and their availability and terms apply.
Plot NDVI observations are recorded manually; the app does not currently fetch
satellite NDVI data. The carbon calculator is a clearly labeled screening proxy,
not a registry methodology or credit-eligibility decision. Marketplace listings
do not process payments or verify counterparties. Public farm and batch counts
are organization-submitted records, not independent verification.

Start a business workspace at `/grove/`. CSV batch imports accept `species`,
`quantity`, and `planted_date` columns, with optional `spacing_m` and
`source_nursery`. Owners/managers can add existing user accounts to their team;
email invitations are not configured. This is an assumption-led Bangladesh MVP;
validate workflows with local farm partners before production rollout.

## Moderation operations

The purpose-built moderator console lives at `/ops/`; Django Admin remains at
`/admin/` for deeper data operations. Run `python manage.py migrate` to install
the Ops schema and create the `Ops Admin`, `Moderator`, `Support`, and `Analyst`
groups. Assign accounts to these groups from Django Admin. Superusers and
`Ops Admin` can read and moderate; `Moderator` can review reports and AI flags;
`Support` and `Analyst` are read-only. Ordinary accounts cannot access the
console.

Members can report public posts, comments, and profiles. Moderators can dismiss
reports, warn an account via an in-app notification, or hide/remove a post or
comment. Every decision requires a reason and stores a before/after snapshot in
the read-only audit interface. Hidden and removed content is excluded from
public feeds and search; owners can still view their hidden posts. AI flags are
reviewable records, but automated content detection and Perspective API
integration are not enabled in this MVP.

## Footer and newsletter

The shared Canopy footer includes responsive navigation, the browser-native
PWA install prompt where supported, language selection, and a database-backed
newsletter opt-in list. Newsletter emails are not sent yet; configure a
transactional email provider before offering newsletter delivery. Subscribers
can unsubscribe from the confirmation link shown after signup. Django Admin
lists subscriber addresses and subscription status.

Optional footer destinations are configured with `CANOPY_SUPPORT_EMAIL`,
`CANOPY_FACEBOOK_URL`, `CANOPY_INSTAGRAM_URL`, `CANOPY_X_URL`,
`CANOPY_YOUTUBE_URL`, `CANOPY_LINKEDIN_URL`, `CANOPY_GOOGLE_PLAY_URL`,
`CANOPY_PRIVACY_URL`, `CANOPY_TERMS_URL`, `CANOPY_COOKIE_POLICY_URL`,
`CANOPY_ACCESSIBILITY_URL`, and `CANOPY_GUIDELINES_URL`. Social, store, legal,
and guidelines links are omitted until a valid HTTPS destination is configured.
The system-status indicator currently checks database connectivity only.

## Folder Structure
- `tracker/` - Django project settings
- `trees/` - Community app (models, views, templates, forms)
- `grove/` - Farm workspace, plots, batches, tasks, memberships, and health analyses
- `grove_market/`, `grove_finance/`, `grove_carbon/`, `grove_compliance/` - Modular business features
- `ops/` - Role-restricted moderation console, reports, AI flag queue, and audit log
- `media/` - Uploaded images (tree and profile pictures)
- `templates/` - HTML templates (feed, auth, profile, etc.)

## Notes
- Only logged-in users can add, react, comment, or delete posts.
- All posts are visible to everyone.
- Profile and password management are available from the profile page.

## License
MIT License

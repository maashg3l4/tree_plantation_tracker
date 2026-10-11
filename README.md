# Tree Plantation Social Tracker

A Django-based social platform for tracking tree plantation activities, inspired by Facebook's social feed. Users can register, log in, share trees, react, comment, and manage their profiles in a modern, interactive feed.

## Features

- **User Registration & Authentication**
  - Register, log in, and log out securely
  - Edit profile (username, email, password, profile picture)

- **Social Feed**
  - Public home page shows all tree posts from all users
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

- **Modern UI/UX**
  - Responsive, card-based feed with Tailwind CSS, Alpine.js, and HTMX
  - Light/dark themes follow system preference and can be overridden manually
  - User avatars (uploaded or auto-generated)
  - Login/Register buttons always visible in navbar
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

## Folder Structure
- `tracker/` - Django project settings
- `trees/` - Main app (models, views, templates, forms)
- `media/` - Uploaded images (tree and profile pictures)
- `templates/` - HTML templates (feed, auth, profile, etc.)

## Notes
- Only logged-in users can add, react, comment, or delete posts.
- All posts are visible to everyone.
- Profile and password management are available from the profile page.

## License
MIT License

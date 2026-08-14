# Memorial Platform

A multi-tenant Flask memorial platform for creating and managing separate family memorials from one application.

## Core features

- Platform owner dashboard
- Unlimited memorials with unique URLs: `/m/<slug>`
- Separate family password for every memorial
- Family dashboard for biography, funeral details, M-Pesa, WhatsApp and livestream
- Direct portrait and photo gallery uploads
- Three memorial themes
- Separate condolence wall for every memorial
- Family acknowledgement of tributes
- Hide/show/delete moderation
- Draft and publish controls
- PostgreSQL support for Render
- SQLite fallback for local development

## Important architecture

Every memorial is a separate tenant record. Tributes and uploaded photographs are linked to a `memorial_id`, preventing one family's information from being mixed with another family's data.

Uploaded images are stored in the database in this MVP. This makes them persistent when the app is hosted on Render with PostgreSQL, without requiring a separate media service. For larger-scale production, move media to Cloudinary, S3 or another object-storage service.

## Run locally

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, set `PLATFORM_ADMIN_PASSWORD`, then:

```bash
python app.py
```

Open:

- Home: `http://127.0.0.1:5000`
- Platform login: `http://127.0.0.1:5000/platform/login`

## Deploy to GitHub

Create a new repository, for example `memorial-platform`, then from this folder:

```bash
git init
git add .
git commit -m "Initial multi-tenant memorial platform"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/memorial-platform.git
git push -u origin main
```

## Deploy to Render

This repository includes `render.yaml`.

1. Push the complete project to GitHub.
2. In Render, choose **New > Blueprint**.
3. Connect the GitHub repository.
4. Render will create the web service and PostgreSQL database from `render.yaml`.
5. When prompted, set `PLATFORM_ADMIN_PASSWORD`.
6. After deployment, open `/platform/login`.

The generated `SECRET_KEY` and PostgreSQL connection are configured through Render.

## First use

1. Log in at `/platform/login`.
2. Create a memorial with a name, slug and family password.
3. The family dashboard opens.
4. Upload the main portrait and gallery photographs.
5. Add biography, funeral details, contribution information and WhatsApp links.
6. Preview the memorial.
7. Turn on **Publish this memorial publicly** and save.

## URLs

For a memorial created with slug `mary-achieng`:

Public memorial:

`/m/mary-achieng`

Family dashboard:

`/m/mary-achieng/family`

Family login:

`/m/mary-achieng/family/login`

## Before commercial launch

Recommended next additions:

- Named user accounts instead of shared family passwords
- Password reset and email invitations
- Cloudinary/S3 media storage
- Flask-Migrate/Alembic migrations
- Subscription/payment plans
- Audit logs
- Custom domains
- Memorial analytics
- Privacy policy, terms and data-retention controls
- Backup/export tools for families

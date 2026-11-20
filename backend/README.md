# Backend: Pet Monitor API and Dashboard

A Laravel 13 app that receives episodes from `gateway/gateway.py`, stores them in SQLite and shows them on a dashboard.

```bash
composer install
cp .env.example .env
php artisan key:generate
touch database/database.sqlite
php artisan migrate
php artisan serve        # http://127.0.0.1:8000
php artisan test         # API tests in tests/Feature/EpisodeApiTest.php
```

| Route | Purpose |
|---|---|
| `POST /api/episodes` | Ingest an episode. It's idempotent on `event_id`: 201 when created, 200 when a replay updates the row |
| `GET /api/episodes` | The 100 most recent episodes as JSON |
| `GET /` | Dashboard |
| `GET /export` | CSV export of every episode |

The project-specific code is in `app/Http/Controllers/EpisodeController.php`, `app/Models/Episode.php`, `database/migrations/*_create_episodes_table.php`, `routes/` and `resources/views/dashboard.blade.php`. Everything else is the standard Laravel skeleton.

The API has **no authentication**. See [../docs/deployment_notes.md](../docs/deployment_notes.md) before exposing it.

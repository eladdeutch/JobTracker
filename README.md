# 🎯 Job Application Tracker

A powerful web application to track your job applications, scan Gmail for job-related emails, and organize your job search.

## Features

- **📧 Gmail Integration**: Automatically scan your inbox for job-related emails
- **🔍 Smart Extraction**: Uses pattern matching to extract company names, positions, and application status
- **📊 Dashboard**: Visual overview of your job search progress
- **📈 Analytics**: Track response rates, interview rates, and average response times
- **⏰ Reminders**: Set follow-up reminders for applications
- **📤 Export**: Export your data (coming soon)

## Tech Stack

- **Backend**: Python + Flask
- **Database**: PostgreSQL
- **Frontend**: HTML/CSS/JavaScript (Vanilla)
- **Authentication**: Google OAuth 2.0 for Gmail access

## Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Google Cloud Project with Gmail API enabled

## Setup

### 1. Clone and Install Dependencies

```bash
cd "C:\Projects\MCP Server\job-tracker"
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL Database

```sql
CREATE DATABASE job_tracker;
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
copy .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/job_tracker
FLASK_SECRET_KEY=your-random-secret-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### 4. Set Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Gmail API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Select "Web application"
6. Add authorized redirect URI: `http://localhost:5000/auth/callback`
7. Copy Client ID and Client Secret to your `.env` file

### 5. Run the Application

```bash
python run.py
```

Open http://localhost:5000 in your browser.

## Usage

### Dashboard
- View overall statistics
- See response rates and interview rates
- Track recent activity

### Applications
- Add applications manually
- Edit status and details
- Set follow-up reminders
- Search and filter

### Email Scanner
1. Connect your Gmail account (click "Connect Gmail" in sidebar)
2. Click "Scan Emails" to search for job-related emails
3. Review detected emails and create applications
4. Use "Auto-Process" for high-confidence matches

### Reminders
- Create follow-up reminders for applications
- View due and upcoming reminders
- Snooze or complete reminders

## API Endpoints

### Authentication
- `GET /auth/gmail/login` - Get Gmail OAuth URL
- `GET /auth/callback` - OAuth callback
- `GET /auth/gmail/status` - Check connection status
- `POST /auth/gmail/disconnect` - Disconnect Gmail

### Applications
- `GET /api/applications` - List applications
- `GET /api/applications/:id` - Get single application
- `POST /api/applications` - Create application
- `PUT /api/applications/:id` - Update application
- `DELETE /api/applications/:id` - Delete application
- `PATCH /api/applications/:id/status` - Update status

### Emails
- `POST /api/emails/scan` - Scan Gmail for job emails
- `GET /api/emails/unprocessed` - Get unprocessed emails
- `POST /api/emails/:id/create-application` - Create app from email
- `POST /api/emails/:id/dismiss` - Dismiss email
- `POST /api/emails/auto-process` - Auto-process high-confidence emails

### Reminders
- `GET /api/reminders` - List reminders
- `GET /api/reminders/due` - Get due reminders
- `POST /api/reminders` - Create reminder
- `POST /api/reminders/:id/complete` - Complete reminder
- `POST /api/reminders/:id/snooze` - Snooze reminder

### Statistics
- `GET /api/stats/dashboard` - Full dashboard stats
- `GET /api/stats/status-breakdown` - Status breakdown
- `GET /api/stats/response-rates` - Response rates

## Project Structure

```
job-tracker/
├── backend/
│   ├── models/          # SQLAlchemy models
│   ├── routes/          # Flask blueprints
│   ├── services/        # Business logic
│   ├── config.py        # Configuration
│   └── app.py           # Flask app factory
├── frontend/
│   ├── css/
│   │   └── styles.css   # Styles
│   ├── js/
│   │   ├── api.js       # API client
│   │   └── app.js       # Main app
│   └── index.html       # Main HTML
├── .env.example         # Environment template
├── requirements.txt     # Python dependencies
├── run.py              # Entry point
└── README.md           # This file
```

## Publishing to GitHub (keeping secrets safe)

Before pushing this repo to GitHub:

1. **Never commit `.env`**  
   It’s in `.gitignore`. Confirm it’s not tracked:
   ```bash
   git status
   ```
   If `.env` ever appears, run: `git rm --cached .env` and commit that change.

2. **Use `.env.example` as the template**  
   `.env.example` has placeholder values only. New clones copy it to `.env` and fill in real values locally.

3. **Double-check before first push**
   ```bash
   git status
   git diff --staged
   ```
   Ensure no file under the repo root is named `.env`, `credentials.json`, `token.json`, or similar. Those patterns are in `.gitignore`.

4. **Sensitive values that must stay local**
   - `DATABASE_URL` (Postgres connection string with password)
   - `FLASK_SECRET_KEY`
   - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
   - OAuth tokens are stored in the database, not in the repo.

5. **Optional: private repo**  
   For extra safety, create the GitHub repo as **Private** so only you (and people you invite) can see it.

6. **Run the pre-push check script**  
   Before pushing, run:
   ```bash
   python check-before-push.py
   ```
   It will exit with an error if any sensitive files (e.g. `.env`, `credentials.json`) are staged or untracked, and will warn if such files are already tracked.

   To run the check automatically before every push, create a git pre-push hook:
   ```bash
   # Windows (PowerShell, from repo root)
   echo "python check-before-push.py" > .git/hooks/pre-push
   # Make executable (Git Bash or WSL): chmod +x .git/hooks/pre-push
   ```

## License

MIT

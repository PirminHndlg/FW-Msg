# FW-Msg

## Description
FW-Msg is a comprehensive tool for managing volunteer work. It enables organizations to efficiently manage volunteers, projects, and tasks while providing a user-friendly interface for all stakeholders.

## Features
- Volunteer management and tracking
- Project organization and task assignment
- Team collaboration tools
- Email notifications
- Web push notifications
- Multi-language support (German/English)
- Responsive design

## Prerequisites
- Python 3.8 or higher
- Django 3.0 or higher
- Redis (for Celery tasks)
- SMTP server for email notifications

## Installation

### 1. Clone the Repository
```bash
git clone git@github.com:PirminHndlg/FW-Msg.git
cd FW-Msg
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Settings Setup
```bash
cd FWMsg
cp FWMsg/settings.py.example FWMsg/settings.py
cp FWMsg/.secrets.json.example FWMsg/.secrets.json
```

### 2. Configure Settings
Edit the following files with your specific configuration:

#### settings.py
- Replace `SECRET_KEY` with your own secret key
- Configure database settings if not using SQLite
- Update `ADMINS` and `MANAGERS` with your contact information
- Configure `IFRAMELY_API_KEY` if using Iframely
- Set up `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` for web push notifications
- Update `CSRF_TRUSTED_ORIGINS` with your domain

#### .secrets.json
```json
{
    "server_mail": "noreply@example.com",
    "smtp_server": "smtp.example.com",
    "port": 587,
    "sender_email": "notifications@example.com",
    "password": "your_email_password"
}
```

### 3. Database Setup
> **Note:** Migration files are not included in the repository. You will need to create them using the commands below.

```bash
python manage.py makemigrations Global
python manage.py makemigrations FW
python manage.py makemigrations ORG
python manage.py makemigrations TEAM
python manage.py migrate
python manage.py createsuperuser
```

## Running the Application

### Development Server
```bash
python manage.py runserver
```

### Celery Worker (for background tasks)
```bash
celery -A FWMsg worker -l info
```

### To add a new organization to the system:

1. Go to `http://localhost:8000/admin/` (or your domain if in production)
2. Log in with your superuser credentials
3. Navigate to "ORG" > "Organisations"
4. Click on "Add Organisation" button
5. Fill in the required information
6. Click "Save" to create the new organization
7. An email with login credentials will be automatically sent to the email address you inserted

## Development

### Directory Structure
```
FWMsg/
├── FW/              # Volunteer management app
├── ORG/             # Organization management app
├── Home/            # Home page app
├── Global/          # Global utilities
├── TEAM/            # Team management app
└── FWMsg/           # Project settings
```

### Static Files
Static files are organized in app-specific directories:
- `FW/fw-static/`
- `ORG/org-static/`
- `Global/global-static/`
- `TEAM/team-static/`
- `logos/`

## License
FW-Msg is licensed under the MIT License. This means you can do whatever you want with the code as long as you keep the license.

## Contact
For questions or suggestions, you can reach me at [admin@volunteer.solutions](mailto:admin@volunteer.solutions).

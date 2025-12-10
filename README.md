# Volunteer.solutions

## Description
Volunteer.solutions is a comprehensive tool for managing volunteer work. It enables organizations to efficiently manage volunteers, projects, and tasks while providing a user-friendly interface for all stakeholders.

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
- Django 4.2 or higher
- Node.js 16 or higher (for frontend dependencies)
- Redis (for Celery tasks and caching)
- SMTP server for email notifications
- VAPID keys for web push notifications (optional)

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

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies
```bash
npm install
```

See [FRONTEND_SETUP.md](FRONTEND_SETUP.md) for more details about frontend dependency management.

## Configuration

### 1. Settings Setup
```bash
cd FWMsg
cp FWMsg/example-settings.py FWMsg/settings.py
```

### 2. Configure Settings
Create a `.secrets.json` file in the `FWMsg/FWMsg/` directory with your configuration. The settings.py file will automatically load these secrets.

#### .secrets.json
```json
{
    "// Django Core Settings": "==========================================",
    "secret_key": "REPLACE_WITH_YOUR_SECRET_KEY",
    "debug": true,
    "// Domain & Hosting Settings": "=====================================",
    "domain": "yourdomain.com",
    "domain_host": "https://yourdomain.com",
    "allowed_hosts": ["yourdomain.com", "www.yourdomain.com"],
    "// Security Settings": "=============================================",
    "csrf_trusted_origins": ["https://yourdomain.com"],
    "trusted_orgins": ["*"],
    "// Email Configuration": "===========================================",
    "server_mail": "noreply@example.com",
    "smtp_server": "smtp.example.com",
    "port": 587,
    "sender_email": "notifications@example.com",
    "password": "your_email_password",
    "feedback_email": "admin@example.com",
    "imap_server": "imap.example.com",
    "imap_port": 993,
    "imap_use_ssl": true,
    "// Admin Configuration": "===========================================",
    "admins": [
        ["Admin Name", "admin@example.com"]
    ],
    "// Push Notification Settings": "=====================================",
    "vapid_public_key": "YOUR_VAPID_PUBLIC_KEY",
    "vapid_private_key": "YOUR_VAPID_PRIVATE_KEY"
}
```

**Important:** 
- Replace all placeholder values with your actual configuration
- The `secret_key` should be a secure random string
- For production, set `debug` to `false` and use proper domain values
- Make sure to add `.secrets.json` to your `.gitignore` file to keep secrets secure

### 3. Collect Static Files

```bash
cd FWMsg
python manage.py collectstatic --noinput
```

### 4. Database Setup

```bash
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

### Celery Beat
```bash
celery -A FWMsg beat
```

### To add a new organization to the system:

1. Go to `http://localhost:8000/` (or your domain if in production)
2. Log in with your superuser credentials
3. Go to `http://localhost:8000/administrator/` (or your domain if in production)
4. Add a new organisation by filling in the required fields and saving
5. An email with login credentials will be automatically sent to the email address you inserted

## Development

### Directory Structure
```
FWMsg/
├── FW/              # Volunteer management app
├── ORG/             # Organization management app
├── Home/            # Home page app
├── Global/          # Global utilities
├── TEAM/            # Team management app
├── ADMIN/           # Admin interface app
├── BW/              # Application management app
├── Ehemalige/       # Alumni management app
├── seminar/         # Seminar management app
├── survey/          # Survey management app
└── FWMsg/           # Project settings
```

### Static Files

Frontend libraries (Bootstrap, jQuery, Font Awesome, etc.) are managed via npm. See [FRONTEND_SETUP.md](FRONTEND_SETUP.md) for details.

App-specific static files are organized in directories:
- `FW/fw-static/`
- `ORG/org-static/`
- `Global/global-static/`
- `Home/home-static/`
- `seminar/seminar-static/`
- `logos/`

Note: Some apps like `TEAM`, `ADMIN`, `BW`, `Ehemalige`, and `survey` don't have dedicated static directories and rely on global static files.

## License
Volunteer.solutions is licensed under the GNU General Public License v3.0 (GPL v3). This is a copyleft license that ensures the software remains free and open source. You are free to use, modify, and distribute the code, but any derivative works must also be licensed under GPL v3. See the [LICENSE](LICENSE) file for the full license text.

## Contact
For questions or suggestions, you can reach me at [admin@volunteer.solutions](mailto:admin@volunteer.solutions).

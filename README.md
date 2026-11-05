# Content Hosting System

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/Django-5.0+-green.svg)](https://www.djangoproject.com/)


A secure, auditable content hosting platform built with Django. Manage multi-language content uploads with creator-approver workflow, automatic archiving, and complete audit trails.

## Table of Contents

1. [Features](#features)
2. [Architecture Overview](#architecture-overview)
3. [Directory Structure](#directory-structure)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [User Roles & Permissions](#user-roles--permissions)
7. [Storage System](#storage-system)
8. [Audit Logging](#audit-logging)
9. [Testing](#testing)

---

## Features

- **Role-Based Access Control**: Separate dashboards for Content Creators and Approvers with custom decorators
- **Multi-Language Support**: Built-in support for English and German with easy extension for more languages
- **Secure Upload System**: SHA-256 hashing with salt for content deduplication and integrity verification
- **Hard-Link Storage**: Efficient filesystem storage using hard links (no duplicate files across versions)
- **Complete Audit Trail**: Every action logged with actor, timestamp, and detailed metadata
- **Test/Production Workflow**: Preview in test environment before publishing to production
- **Automatic Pruning**: Configurable cleanup of old logs and archive files via management command
- **Password Reset**: Secure email-based password recovery with token validation
- **HTMX Integration**: Dynamic table updates without page reloads

---

## Architecture Overview

### Request Flow

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│    User      │────▶│    Django    │────▶│   View Logic    │────▶│  Response   │
│   Request    │     │    URLs      │     │(Creator/Approver│     │  (Template/ │
│              │     │              │     │  Dashboards)    │     │   Redirect) │
└──────────────┘     └──────────────┘     └─────────────────┘     └─────────────┘
                                                  │
                                                  ▼
                                        ┌─────────────────┐
                                        │  Models Layer   │
                                        │ (UploadHistory, │
                                        │  LiveState,     │
                                        │  ActionLog)     │
                                        └─────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
            ┌───────────────┐            ┌───────────────┐            ┌───────────────┐
            │    Database   │            │    Storage    │            │    Audit      │
            │   (SQLite/    │            │   (Filesystem │            │    (Action    │
            │   PostgreSQL) │            │   with Hard   │            │    Logging)   │
            │               │            │    Links)     │            │               │
            └───────────────┘            └───────────────┘            └───────────────┘
```

### Core Django Apps

| App | Purpose | Key Components |
|-----|---------|----------------|
| `users` | Custom authentication with roles | `CustomUser` model, role decorators (`creator_required`, `approver_required`), password reset views |
| `content` | Upload management & file handling | `UploadHistory`, `LiveState` models, SHA-256 hashing, filesystem operations |
| `audit` | Comprehensive action logging | `ActionLog` model with JSON metadata, log aggregation services |
| `config` | Project configuration | Settings with python-dotenv, URL routing, middleware stack |

---

## Directory Structure

```
content_hosting_system/
│
├── config/                          # Django project configuration
│   ├── __init__.py
│   ├── settings.py                  # Main settings (env-based config)
│   ├── urls.py                      # Root URL configuration
│   ├── wsgi.py                      # WSGI entry point
│   └── asgi.py                      # ASGI entry point
│
├── users/                           # Custom user authentication
│   ├── __init__.py
│   ├── admin.py                     # CustomUser admin configuration
│   ├── apps.py
│   ├── decorators.py                # @creator_required, @approver_required
│   ├── forms.py                     # Registration, password reset forms
│   ├── models.py                    # CustomUser with is_creator/is_approver flags
│   ├── signals.py                   # User creation signals
│   ├── urls.py                      # /login/, /logout/, /register/, /password-reset/*
│   ├── views.py                     # Authentication views
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
│
├── content/                         # Core content management
│   ├── __init__.py
│   ├── admin.py                     # UploadHistory, LiveState admin
│   ├── apps.py
│   ├── constants.py                 # STATUS_CHOICES, ACTION_TYPE_CHOICES, ENV_CHOICES
│   ├── forms.py                     # UploadForm with file validation
│   ├── models.py                    # UploadHistory, LiveState models
│   ├── urls.py                      # /upload/, /reupload/, /dashboard/, /test/*, /production/*
│   ├── views.py                     # Creator/Approver dashboards, serve content
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   └── 0002_uploadhistory_deleted_at_uploadhistory_deleted_by_and_more.py
│   │
│   ├── utils/                       # Utility modules
│   │   ├── __init__.py
│   │   ├── filesystem.py            # Hard link operations, directory management
│   │   ├── hashing.py               # SHA-256 with salt content hashing
│   │   └── validators.py            # File extension, MIME type validation
│   │
│   ├── tests/                       # Comprehensive test suite
│   │   ├── __init__.py
│   │   ├── test.py                  # Basic model tests
│   │   ├── test_filesystem.py       # Hard link operation tests
│   │   ├── test_hashing.py          # Hashing utility tests
│   │   ├── test_validators.py       # File validation tests
│   │   └── test_views.py            # Dashboard view tests
│   │
│   ├── management/                  # Custom management commands
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── prune.py             # python manage.py prune
│   │
│   └── forms.py                     # Upload forms with validation
│
├── audit/                           # Audit logging system
│   ├── __init__.py
│   ├── admin.py                     # ActionLog admin
│   ├── apps.py
│   ├── models.py                    # ActionLog with JSON metadata
│   ├── services.py                  # Log aggregation queries
│   ├── urls.py                      # /audit/logs/
│   ├── views.py                     # Log viewing (approvers only)
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   └── 0002_alter_actionlog_action_type.py
│   └── tests/
│       ├── __init__.py
│       ├── test.py
│       ├── test_services.py         # Log query tests
│       └── test_views.py            # Audit view tests
│
├── templates/                       # Django templates
│   ├── base.html                    # Base layout with Bootstrap 5
│   ├── 403.html                     # Forbidden
│   ├── 404.html                     # Not Found
│   ├── 500.html                     # Server Error
│   │
│   ├── users/                       # Authentication templates
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── password_reset.html
│   │   ├── password_reset_confirm.html
│   │   ├── password_reset_done.html
│   │   ├── password_reset_complete.html
│   │   ├── password_reset_email.txt
│   │   └── password_reset_subject.txt
│   │
│   ├── content/                     # Content management templates
│   │   ├── creator_dashboard.html   # Creator view
│   │   ├── approver_dashboard.html  # Approver view
│   │   ├── upload.html
│   │   ├── reupload.html
│   │   └── partials/                # HTMX partials
│   │       ├── creator_table.html
│   │       └── approver_tables.html
│   │
│   ├── audit/                       # Audit templates
│   │   ├── logs.html
│   │   └── partials/
│   │       └── logs_table.html
│   │
│   └── test-product12/              # Example uploaded content
│       ├── en/
│       │   ├── index.html
│       │   └── style.css
│       └── de/
│           ├── index.html
│           └── style.css
│
├── static/                          # Static assets
│   ├── css/
│   │   └── style.css                # Custom styles
│   └── js/
│       └── table_controls.js        # HTMX table interactions
│
├── storage/                         # File storage (gitignored contents)
│   ├── .gitkeep
│   │
│   ├── archive/                     # Permanent content archives
│   │   ├── .gitkeep
│   │   └── {sha256_hash}/           # Each upload gets a hash-named folder
│   │       ├── en/                  # Language subdirectories
│   │       │   ├── index.html
│   │       │   └── style.css
│   │       └── de/
│   │
│   └── working/                     # Hard links to current deployments
│       ├── .gitkeep
│       ├── test/                    # Test environment deployments
│       │   ├── .gitkeep
│       │   └── {sha256_hash}/       # Hard linked to archive
│       │       ├── en/
│       │       └── de/
│       └── production/              # Production environment deployments
│           ├── .gitkeep
│           └── {sha256_hash}/
│               ├── en/
│               └── de/
│
├── manage.py                        # Django management entry point
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (gitignored)
└── .gitignore                       # Git exclusions

```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Step-by-Step Setup

**1. Clone the Repository**

```bash
git clone https://code.mumbai-tech.com/gen/djpages.git
cd djpages/content_hosting_system
```

**2. Create Virtual Environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install Dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure Environment**

Create a `.env` file:

```bash
cp .env.example .env  # Or create manually
```

Edit `.env` with your settings (see [Configuration](#configuration)).

**5. Initialize Database**

```bash
python manage.py migrate
```

**6. Create Superuser**

```bash
python manage.py createsuperuser
```

**7. Create Storage Directories**

```bash
python manage.py create_storage_dirs
```

**8. Run Development Server**

```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/

---

## Configuration

### Required Environment Variables

Create a `.env` file in the project root:

```env
# SECURITY
DJANGO_SECRET_KEY=your-secret-key-change-in-production

# DEBUG (set to False in production)
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# DATABASE (SQLite for dev, PostgreSQL for production)
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3

# STORAGE PATHS
STORAGE_ROOT=storage
WORKING_DIR=storage/working
ARCHIVE_DIR=storage/archive

# UPLOAD LIMITS
MAX_UPLOAD_SIZE_MB=500
ALLOWED_FILE_EXTENSIONS=.html,.css,.js,.jpg,.jpeg,.png,.gif,.svg,.ico,.json,.xml,.txt

# SECURITY SALT (change in production)
SALT_VALUE=change-this-in-production

# EMAIL (for password reset)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# PRUNING (days to retain)
PRUNE_LOG_DAYS=365
PRUNE_ARCHIVE_DAYS=365
```

---

### Workflow States

| Status | Description | Available Actions |
|--------|-------------|-------------------|
| `PENDING` | Awaiting approver review | Approve, Reject |
| `APPROVED` | Approved, deployed to test | Publish to Production, Reject |
| `REJECTED` | Rejected with reason | Re-upload (creates new hash) |
| `PUBLISHED` | Live in production | Unpublish |
| `UNPUBLISHED` | Removed from production | Re-upload, Delete |
| `DELETED` | Soft deleted (retains archive) | Restore |
| `ARCHIVED` | Pruned from working, archive retained | - |

---

## User Roles & Permissions

### Role Matrix

| Action | Superuser | Creator | Approver |
|--------|-----------|---------|----------|
| Create Uploads | ✅ | ✅ | ❌ |
| View Own Uploads | ✅ | ✅ | ❌ |
| Re-upload Content | ✅ | ✅ | ❌ |
| View All Uploads | ✅ | ❌ | ✅ |
| Approve/Reject | ✅ | ❌ | ✅ |
| Deploy to Production | ✅ | ❌ | ✅ |
| View Audit Logs | ✅ | ❌ | ✅ |
| Manage Users | ✅ | ❌ | ❌ |

### Access Decorators

```python
# content/views.py usage
from users.decorators import creator_required, approver_required

@creator_required
def creator_dashboard(request):
    # Only creators can access
    ...

@approver_required
def approver_dashboard(request):
    # Only approvers can access
    ...
```

---

## Storage System

### Storage Commands

```bash
# Manual prune old archives and logs
python manage.py prune

# Verify hard links
ls -li storage/archive/{hash}/en/index.html storage/working/test/{hash}/en/index.html
# Same inode = hard link working correctly
```

---

## Audit Logging

All significant actions are automatically logged to the `ActionLog` model:

### Logged Actions

| Action Type | When Triggered | Metadata Captured |
|-------------|----------------|-------------------|
| `UPLOAD_CREATED` | Creator uploads content | hash, filename, file_count, total_size |
| `UPLOAD_APPROVED` | Approver approves | hash, approver, timestamp |
| `UPLOAD_REJECTED` | Approver rejects | hash, reason, actor |
| `UPLOAD_PUBLISHED` | Deployed to production | hash, environment, actor |
| `UPLOAD_UNPUBLISHED` | Removed from production | hash, reason, actor |
| `UPLOAD_DELETED` | Soft delete | hash, deleted_by |
| `UPLOAD_RESTORED` | Restore deleted upload | hash, restored_by |
| `UPLOAD_REUPLOADED` | Creator re-uploads | old_hash, new_hash, replaces |

### Audit Log Structure

```python
# audit/models.py
class ActionLog:
    timestamp: DateTime      # When action occurred
    actor: ForeignKey         # Who performed the action
    action_type: CharField    # Type of action (choices)
    related_hash: CharField   # Content hash reference
    details: JSONField        # Flexible metadata storage
```

### Viewing Logs

Approvers can view the complete audit trail at `/audit/logs/`:
- Filterable by action type
- Searchable by content hash
- Shows actor, timestamp, and detailed metadata

---

## Testing

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test users
python manage.py test content
python manage.py test audit

# Run with verbosity
python manage.py test --verbosity=2
```

### Test Coverage

| Module | Test File | Coverage |
|--------|-----------|----------|
| Content Models | `content/tests/test.py` | UploadHistory, LiveState CRUD |
| Filesystem Utils | `content/tests/test_filesing.py` | Hard link operations |
| Hashing | `content/tests/test_hashing.py` | SHA-256 with salt |
| Validators | `content/tests/test_validators.py` | File extension, MIME |
| Views | `content/tests/test_views.py` | Dashboard permissions |
| Decorators | `users/tests/test_decorators.py` | Role-based access |
| Audit Services | `audit/tests/test_services.py` | Log aggregation |

### Manual Testing Checklist

```
□ User Registration & Login
  □ Create account with creator role
  □ Login with valid credentials
  □ Access denied for wrong role URLs

□ Password Reset Flow
  □ Request password reset
  □ Click email link
  □ Set new password
  □ Login with new password

□ Content Upload
  □ Creator uploads ZIP file
  □ File validation (size, extensions)
  □ Hash generation
  □ Archive creation

□ Approval Workflow
  □ Approver sees pending uploads
  □ Approve → deploys to test
  □ Reject → reason recorded
  □ Creator sees rejection reason

□ Re-upload
  □ Creator re-uploads rejected content
  □ New hash generated
  □ Link to previous version preserved
  □ Audit log shows chain

□ Production Deployment
  □ Publish from test to production
  □ Verify hard links created
  □ Multi-language content accessible

□ Audit & Logging
  □ All actions logged correctly
  □ Log view accessible to approvers
  □ Metadata complete

□ Storage Pruning
  □ Run python manage.py prune
  □ Old archives cleaned
  □ Logs retained per config
```





---

**Built with Django** | Secure Content Management with Complete Audit Trails

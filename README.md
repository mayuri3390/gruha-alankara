# Gruha Alankara - AI Interior Design Platform
AI-powered interior design platform with AR visualization, intelligent furniture recommendations, and real-time design chat.

Team members :- Mayuri Dhum ,
                Omkar Sonawane

Team ID - 699d5f7cfdf409fdbd1bebfc 

## Features

- **AI Design Suggestions** — Get recommendations based on room type, style, and budget
- **AR Furniture Visualization** — Preview furniture in your space
- **User Authentication** — Secure login with optional 2FA
- **Furniture Catalog** — Browse and book furniture items
- **Real-Time Chat** — Design buddy chat with multi-language support
- **Design History** — Save and manage your projects

## Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-SocketIO
- **AI/ML**: Hugging Face Transformers, PyTorch
- **Database**: SQLite
- **Frontend**: HTML/CSS/JavaScript, AR.js
- **Security**: CSRF protection, password hashing, rate limiting

## Installation

1. Clone repository and navigate to folder
2. Create virtual environment: `python -m venv venv`
3. Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. Install dependencies: `pip install -r requirements.txt`
5. Initialize DB:
   ```python
   from app import app, db
   with app.app_context():
       db.create_all()
   ```
6. Run: `python app.py`

Access at `http://localhost:5000`

## Quick Start

1. **Register** — Create account at `/register`
2. **Generate Design** — Go to design page, select preferences, upload room image
3. **View Catalog** — Browse furniture recommendations
4. **AR Preview** — Visualize furniture in your space
5. **Book Furniture** — Complete booking with contact info

## File Structure

```
├── app.py              # Main Flask app
├── ai_engine.py        # Design suggestion engine
├── models.py           # Database models
├── config.py           # Configuration
├── database/           # SQLite database
├── static/             # Images, styles, scripts
├── templates/          # HTML pages
└── requirements.txt    # Dependencies
```

## Database Models

| Model | Purpose |
|-------|---------|
| User | Authentication, 2FA, profiles |
| Design | Saved designs, suggestions, history |
| Furniture | Catalog items, AR models, prices |
| Booking | Furniture orders and status |
| ChatHistory | Real-time chat logs |

## Configuration

Edit `config.py` to change:
- `SECRET_KEY` — Flask secret
- `SQLALCHEMY_DATABASE_URI` — Database path
- `UPLOAD_FOLDER` — File upload directory
- `MAX_CONTENT_LENGTH` — Max file size (16MB default)

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/register` | POST | User registration |
| `/login` | POST | User login |
| `/generate-design` | POST | AI design suggestions |
| `/catalog` | GET | Furniture catalog |
| `/book-furniture` | POST | Book furniture |
| `/setup-2fa` | GET | Enable 2FA |

## Security Features

- Password hashing with werkzeug
- CSRF protection on forms
- Rate limiting on requests
- Image validation (magic bytes)
- XSS prevention with Bleach

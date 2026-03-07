from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(100), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    totp_secret   = db.Column(db.String(32), nullable=True)
    is_2fa_enabled= db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class Design(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    image_path = db.Column(db.String(200))
    room_type  = db.Column(db.String(100))
    style      = db.Column(db.String(100), index=True)
    budget     = db.Column(db.String(50))
    suggestion = db.Column(db.Text)
    confidence = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Composite index for the most common query pattern
    __table_args__ = (
        db.Index('ix_design_user_created', 'user_id', 'created_at'),
    )


class Furniture(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), index=True)
    category    = db.Column(db.String(100), index=True)
    style       = db.Column(db.String(100), index=True)
    price       = db.Column(db.Float)
    description = db.Column(db.Text)
    image_url   = db.Column(db.String(300))
    ar_model    = db.Column(db.String(300))
    in_stock    = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (
        db.Index('ix_furniture_style_category', 'style', 'category'),
    )


class Booking(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, nullable=True, index=True)
    furniture_id   = db.Column(db.Integer, db.ForeignKey('furniture.id'))
    furniture      = db.relationship('Furniture', backref='bookings')
    customer_name  = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    status         = db.Column(db.String(50), default='pending', index=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


class ChatHistory(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), index=True)
    role       = db.Column(db.String(20))
    message    = db.Column(db.Text)
    language   = db.Column(db.String(20), default='en')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
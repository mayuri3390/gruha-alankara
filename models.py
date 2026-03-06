from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Design(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    image_path = db.Column(db.String(200))
    room_type = db.Column(db.String(100))
    style = db.Column(db.String(100))
    budget = db.Column(db.String(50))
    suggestion = db.Column(db.Text)
    confidence = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Furniture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category = db.Column(db.String(100))
    style = db.Column(db.String(100))
    price = db.Column(db.Float)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(300))
    ar_model = db.Column(db.String(300))
    in_stock = db.Column(db.Boolean, default=True)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    furniture_id = db.Column(db.Integer, db.ForeignKey('furniture.id'))
    furniture = db.relationship('Furniture', backref='bookings')
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100))
    role = db.Column(db.String(20))   # 'user' or 'buddy'
    message = db.Column(db.Text)
    language = db.Column(db.String(20), default='en')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
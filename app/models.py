from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db


def utcnow():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(40), nullable=False, default='Public User')
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    hazard_type = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, default=True, nullable=False)
    observations = db.relationship('Observation', backref='location', cascade='all, delete-orphan')

class Observation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    source = db.Column(db.String(180), nullable=False)
    observation_type = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    observed_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    status = db.Column(db.String(40), default='Pending review', nullable=False)
    is_demo = db.Column(db.Boolean, default=True, nullable=False)

class RiskAssessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    level = db.Column(db.String(40), nullable=False, default='Unknown')
    rationale = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    is_demo = db.Column(db.Boolean, default=True, nullable=False)
    location = db.relationship('Location')

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    severity = db.Column(db.String(40), nullable=False, default='Watch')
    status = db.Column(db.String(40), nullable=False, default='Draft')
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    is_demo = db.Column(db.Boolean, default=True, nullable=False)
    location = db.relationship('Location')

class PreparednessResource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)

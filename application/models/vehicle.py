from datetime import datetime
from app import db

class Vehicle(db.Model):
    __tablename__ = 'vehicle'

    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    reg_number = db.Column(db.String(20), unique=True, nullable=False)

    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    driver = db.relationship('Driver', back_populates='vehicles')

    maintenances = db.relationship('Maintenance', back_populates='vehicle')
    routes = db.relationship('Route', back_populates='vehicle')

    def __repr__(self):
        return f"<Vehicle {self.reg_number}>"

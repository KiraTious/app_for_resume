from datetime import datetime, date
from app import db

class Maintenance(db.Model):
    __tablename__ = 'maintenance'

    id = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String(20), nullable=False, default='service')
    type_of_work = db.Column(db.String(100), nullable=True)
    cost = db.Column(db.Float, nullable=False)

    event_date = db.Column(db.Date, nullable=False, default=date.today)
    mileage_km = db.Column(db.Integer, nullable=True)
    fuel_volume_l = db.Column(db.Float, nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicle = db.relationship('Vehicle', back_populates='maintenances')

    def __repr__(self):
        return f"<Maintenance {self.type_of_work} cost={self.cost}>"

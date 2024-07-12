from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String, unique=True, index=True)
    name = db.Column(db.String)
    is_haccp = db.Column(db.Boolean)
    factory = db.Column(db.String)
    product = db.Column(db.String)
    process = db.Column(db.String)
    status = db.Column(db.String)
    introduction_year = db.Column(db.Integer)
    introduction_month = db.Column(db.Integer)
    maintenance_cycle = db.Column(db.Integer)
    manager = db.Column(db.String)
    phone_number = db.Column(db.String)

class MaintenanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String, db.ForeignKey('equipment.equipment_id'))
    maintenance_date = db.Column(db.Date)
    description = db.Column(db.String)
    cost = db.Column(db.Float)
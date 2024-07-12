from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from models import db, Equipment, MaintenanceRecord
from datetime import date, datetime
import json
from flask import send_file
import io
import csv

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///equipment_maintenance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # 세션을 위한 시크릿 키 설정

db.init_app(app)

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

def create_database():
    with app.app_context():
        db.create_all()


@app.route('/')
def index():
    total_equipment = Equipment.query.count()
    total_records = MaintenanceRecord.query.count()
    total_cost = db.session.query(func.sum(MaintenanceRecord.cost)).scalar() or 0
    recent_records = db.session.query(MaintenanceRecord, Equipment.name.label("equipment_name"))\
        .join(Equipment, MaintenanceRecord.equipment_id == Equipment.equipment_id)\
        .order_by(MaintenanceRecord.maintenance_date.desc())\
        .limit(5).all()
    
    return render_template("index.html", 
                           total_equipment=total_equipment,
                           total_records=total_records,
                           total_cost=total_cost,
                           recent_records=recent_records)

@app.route('/records')
def view_records():
    equipment_id = request.args.get('equipment_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = db.session.query(MaintenanceRecord, Equipment).join(Equipment)
    
    if equipment_id:
        query = query.filter(Equipment.equipment_id == equipment_id)
    
    if start_date:
        query = query.filter(MaintenanceRecord.maintenance_date >= start_date)
    
    if end_date:
        query = query.filter(MaintenanceRecord.maintenance_date <= end_date)
    else:
        end_date = date.today()
    
    records = query.order_by(MaintenanceRecord.maintenance_date.desc()).all()
    equipment_list = Equipment.query.all()
    
    today_date = date.today().isoformat()
    
    return render_template("records.html", 
                           records=records,
                           equipment_list=equipment_list,
                           end_date=end_date.isoformat() if isinstance(end_date, date) else None,
                           today_date=today_date)

@app.route('/add', methods=['GET', 'POST'])
def add_record():
    if request.method == 'POST':
        equipment_id = request.form['equipment_id']
        maintenance_date = datetime.strptime(request.form['maintenance_date'], '%Y-%m-%d').date()
        description = request.form['description']
        cost = float(request.form['cost'])

        equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
        if not equipment:
            flash('Equipment not found', 'error')
            return redirect(url_for('add_record'))
        
        new_record = MaintenanceRecord(
            equipment_id=equipment.equipment_id, 
            maintenance_date=maintenance_date, 
            description=description, 
            cost=cost
        )
        db.session.add(new_record)
        db.session.commit()
        flash('Record added successfully', 'success')
        return redirect(url_for('add_record'))

    equipment_list = Equipment.query.all()
    return render_template("add.html", equipment_list=equipment_list)

@app.route('/edit/<int:record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    record = MaintenanceRecord.query.get_or_404(record_id)
    
    if request.method == 'POST':
        equipment_id = request.form['equipment_id']
        maintenance_date = request.form['maintenance_date']
        description = request.form['description']
        cost = request.form['cost']

        equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
        if not equipment:
            flash('Equipment not found', 'error')
            return redirect(url_for('edit_record', record_id=record_id))
        
        record.equipment_id = equipment.equipment_id
        record.maintenance_date = maintenance_date
        record.description = description
        record.cost = cost
        db.session.commit()
        flash('Record updated successfully', 'success')
        return redirect(url_for('view_records'))

    equipment_list = Equipment.query.all()
    return render_template("edit.html", record=record, equipment_list=equipment_list)

@app.route('/statistics')
def statistics():
    monthly_costs = db.session.query(
        func.strftime("%Y-%m", MaintenanceRecord.maintenance_date).label("month"),
        func.sum(MaintenanceRecord.cost).label("total_cost")
    ).group_by("month").order_by("month").all()
    
    equipment_costs = db.session.query(
        Equipment.name,
        func.sum(MaintenanceRecord.cost).label("total_cost")
    ).join(MaintenanceRecord, Equipment.equipment_id == MaintenanceRecord.equipment_id)\
    .group_by(Equipment.equipment_id).order_by(func.sum(MaintenanceRecord.cost).desc()).all()
    
    return render_template("statistics.html", 
                           monthly_costs=json.dumps([(m[0], float(m[1] or 0)) for m in monthly_costs], cls=DateEncoder),
                           equipment_costs=json.dumps([(e.name, float(e.total_cost or 0)) for e in equipment_costs], cls=DateEncoder))

@app.route('/schedule')
def maintenance_schedule():
    today = date.today()
    scheduled_maintenance = db.session.query(Equipment, MaintenanceRecord)\
        .outerjoin(MaintenanceRecord, Equipment.equipment_id == MaintenanceRecord.equipment_id)\
        .filter(MaintenanceRecord.maintenance_date >= today)\
        .order_by(MaintenanceRecord.maintenance_date).all()
    
    equipment_list = Equipment.query.all()
    
    return render_template("schedule.html", 
                           scheduled_maintenance=scheduled_maintenance,
                           equipment_list=equipment_list)


@app.route('/equipment', methods=['GET', 'POST'])
def equipment_form():
    if request.method == 'POST':
        new_equipment = Equipment(
            equipment_id=request.form['equipment_id'],
            name=request.form['name'],
            is_haccp=request.form['is_haccp'] == "True",
            factory=request.form['factory'],
            product=request.form['product'],
            process=request.form['process'],
            status=request.form['status'],
            introduction_year=int(request.form['introduction_year']),
            introduction_month=int(request.form['introduction_month']),
            maintenance_cycle=int(request.form['maintenance_cycle']),
            manager=request.form['manager'],
            phone_number=request.form['phone_number']
        )
        db.session.add(new_equipment)
        db.session.commit()
        flash('Equipment added successfully', 'success')
        return redirect(url_for('equipment_form'))

    current_year = date.today().year
    return render_template("equipment.html", current_year=current_year)

@app.route('/equipment_list', methods=['GET'])
def equipment_list():
    page = request.args.get('page', 1, type=int)
    name = request.args.get('name', '')
    factory = request.args.get('factory', '')
    product = request.args.get('product', '')
    status = request.args.get('status', '')

    query = Equipment.query

    if name:
        query = query.filter(Equipment.name.like(f'%{name}%'))
    if factory:
        query = query.filter(Equipment.factory.like(f'%{factory}%'))
    if product:
        query = query.filter(Equipment.product.like(f'%{product}%'))
    if status:
        query = query.filter(Equipment.status == status)

    equipments = query.paginate(page=page, per_page=30, error_out=False)

    return render_template('equipment_list.html', equipments=equipments)

@app.route('/export_csv')
def export_csv():
    equipments = Equipment.query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['설비 ID', '설비명', 'HACCP 여부', '공장', '제품', '공정', '상태', '도입 연도', '도입 월', '유지보수 주기', '관리자', '전화번호'])
    
    for equipment in equipments:
        writer.writerow([equipment.equipment_id, equipment.name, equipment.is_haccp, equipment.factory, equipment.product, 
                         equipment.process, equipment.status, equipment.introduction_year, equipment.introduction_month, 
                         equipment.maintenance_cycle, equipment.manager, equipment.phone_number])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='equipments_list.csv')



#애플리케이션 시작 시 테이블 생성
create_database()


if __name__ == "__main__":
    with app.app_context():
        app.run(debug=True)
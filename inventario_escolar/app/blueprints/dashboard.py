from flask import Blueprint, render_template, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app.models import Alumno, Carrera, Expediente, Documento
from app.decorators import active_query
from app.extensions import db
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def root():
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard')
@login_required
def index():
    is_admin = current_user.role.nombre == 'Super Admin'
    
    # Stats for cards
    total_alumnos = active_query(Alumno).count()
    total_expedientes = active_query(Expediente).count()
    
    # A complete expediente could be defined as having at least one 'Entregado' doc (customize as needed)
    # For now, let's just count total documents delivered as a proxy or just pass placeholder values
    expedientes_completos = active_query(Documento).filter_by(estado='Entregado').count()
    tasa_completado = (expedientes_completos / total_expedientes * 100) if total_expedientes > 0 else 0

    stats = {
        'total_alumnos': total_alumnos,
        'total_expedientes': total_expedientes,
        'expedientes_completos': expedientes_completos,
        'tasa_completado': tasa_completado
    }
    
    return render_template('dashboard/index.html', stats=stats, is_admin=is_admin)

@dashboard_bp.route('/dashboard/api/stats')
@login_required
def api_stats():
    # Alumnos por carrera
    carreras_count = db.session.query(Carrera.nombre, func.count(Alumno.id)).\
        join(Alumno, Carrera.id == Alumno.carrera_id).\
        filter(Carrera.is_deleted == False, Alumno.is_deleted == False).\
        group_by(Carrera.nombre).all()
    alumnos_por_carrera = {c: count for c, count in carreras_count}

    def get_estado_counts(tipo_modulo):
        counts = db.session.query(Documento.estado, func.count(Documento.id)).\
            join(Expediente, Documento.expediente_id == Expediente.id).\
            filter(Expediente.tipo_modulo == tipo_modulo, Documento.is_deleted == False, Expediente.is_deleted == False).\
            group_by(Documento.estado).all()
        # Default states
        res = {'Pendiente': 0, 'Entregado': 0, 'Recibido': 0, 'No Realizado': 0}
        for estado, count in counts:
            res[estado] = count
        return res

    is_admin = current_user.role.nombre == 'Super Admin'
    
    data = {
        'alumnos_por_carrera': alumnos_por_carrera,
        'total_alumnos': active_query(Alumno).count(),
        'total_expedientes': active_query(Expediente).count(),
        'expedientes_completos': active_query(Documento).filter_by(estado='Entregado').count(),
    }
    data['tasa_completado'] = (data['expedientes_completos'] / data['total_expedientes'] * 100) if data['total_expedientes'] > 0 else 0

    if is_admin or current_user.role.nombre == 'Practicas':
        data['estados_practicas'] = get_estado_counts('p')
    if is_admin or current_user.role.nombre == 'Servicio':
        data['estados_servicio'] = get_estado_counts('s')
    if is_admin or current_user.role.nombre == 'Vinculacion':
        data['estados_vinculacion'] = get_estado_counts('v')

    return jsonify(data)

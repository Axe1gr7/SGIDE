from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import User, Carrera, Alumno, Role, Expediente, Documento
from app.decorators import roles_required, active_query
from app.services.logic_excel import procesar_excel
from app.services.logic_expediente import registrar_alumno
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
@roles_required('Super Admin')
def before_request():
    pass

# --- USUARIOS ---
@admin_bp.route('/usuarios')
def usuarios():
    page = request.args.get('page', 1, type=int)
    pagination = active_query(User).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/usuarios.html', pagination=pagination)

@admin_bp.route('/usuarios/crear', methods=['GET', 'POST'])
def crear_usuario():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nombre_completo = request.form.get('nombre_completo')
        role_id = request.form.get('role_id')
        
        if active_query(User).filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'danger')
        else:
            user = User(username=username, nombre_completo=nombre_completo, role_id=role_id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('admin.usuarios'))
            
    roles = active_query(Role).all()
    return render_template('admin/usuario_form.html', roles=roles, user=None)

@admin_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
def editar_usuario(id):
    user = active_query(User).filter_by(id=id).first_or_404()
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.nombre_completo = request.form.get('nombre_completo')
        user.role_id = request.form.get('role_id')
        password = request.form.get('password')
        if password:
            user.set_password(password)
        db.session.commit()
        flash('Usuario actualizado.', 'success')
        return redirect(url_for('admin.usuarios'))
        
    roles = active_query(Role).all()
    return render_template('admin/usuario_form.html', roles=roles, user=user)

@admin_bp.route('/usuarios/<int:id>/eliminar', methods=['POST'])
def eliminar_usuario(id):
    user = active_query(User).filter_by(id=id).first_or_404()
    user.is_deleted = True
    db.session.commit()
    flash('Usuario eliminado.', 'success')
    return redirect(url_for('admin.usuarios'))

# --- CARRERAS ---
@admin_bp.route('/carreras')
def carreras():
    carreras_list = active_query(Carrera).all()
    return render_template('admin/carreras.html', carreras=carreras_list)

@admin_bp.route('/carreras/crear', methods=['GET', 'POST'])
def crear_carrera():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        prefijo_id = request.form.get('prefijo_id')
        carrera = Carrera(nombre=nombre, prefijo_id=prefijo_id)
        db.session.add(carrera)
        db.session.commit()
        flash('Carrera creada.', 'success')
        return redirect(url_for('admin.carreras'))
    return render_template('admin/carrera_form.html', carrera=None)

@admin_bp.route('/carreras/<int:id>/editar', methods=['GET', 'POST'])
def editar_carrera(id):
    carrera = active_query(Carrera).filter_by(id=id).first_or_404()
    if request.method == 'POST':
        carrera.nombre = request.form.get('nombre')
        carrera.prefijo_id = request.form.get('prefijo_id')
        db.session.commit()
        flash('Carrera actualizada.', 'success')
        return redirect(url_for('admin.carreras'))
    return render_template('admin/carrera_form.html', carrera=carrera)

@admin_bp.route('/carreras/<int:id>/eliminar', methods=['POST'])
def eliminar_carrera(id):
    carrera = active_query(Carrera).filter_by(id=id).first_or_404()
    carrera.is_deleted = True
    db.session.commit()
    flash('Carrera eliminada.', 'success')
    return redirect(url_for('admin.carreras'))

# --- ALUMNOS ---
@admin_bp.route('/alumnos')
def alumnos():
    page = request.args.get('page', 1, type=int)
    carrera_filter = request.args.get('carrera_filter')
    search = request.args.get('search')
    
    query = active_query(Alumno)
    if carrera_filter:
        query = query.filter_by(carrera_id=carrera_filter)
    if search:
        query = query.filter((Alumno.nombre.ilike(f'%{search}%')) | (Alumno.matricula.ilike(f'%{search}%')))
        
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    carreras_list = active_query(Carrera).all()
    return render_template('admin/alumnos.html', pagination=pagination, carreras=carreras_list, carrera_filter=carrera_filter, search=search)

@admin_bp.route('/alumnos/crear', methods=['GET', 'POST'])
def crear_alumno():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre') or None
            matricula = request.form.get('matricula') or None
            anio_generacion = request.form.get('anio_generacion')
            anio_generacion = int(anio_generacion) if anio_generacion else None
            anio_egreso = request.form.get('anio_egreso')
            anio_egreso = int(anio_egreso) if anio_egreso else None
            estatus = request.form.get('estatus', 'Activo') or 'Activo'
            carrera_id = request.form.get('carrera_id')
            carrera_id = int(carrera_id) if carrera_id else None

            carrera = active_query(Carrera).filter_by(id=carrera_id).first() if carrera_id else None
            registrar_alumno(nombre, matricula, anio_generacion,
                             carrera.id if carrera else None, carrera.prefijo_id if carrera else None,
                             anio_egreso=anio_egreso, estatus=estatus)
            db.session.commit()
            flash('Alumno registrado y expedientes generados.', 'success')
            return redirect(url_for('admin.alumnos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    carreras_list = active_query(Carrera).all()
    return render_template('admin/alumno_form.html', carreras=carreras_list, alumno=None)

@admin_bp.route('/alumnos/<int:id>/editar', methods=['GET', 'POST'])
def editar_alumno(id):
    alumno = active_query(Alumno).filter_by(id=id).first_or_404()
    if request.method == 'POST':
        alumno.nombre = request.form.get('nombre') or None
        alumno.matricula = request.form.get('matricula') or None
        anio_generacion = request.form.get('anio_generacion')
        alumno.anio_generacion = int(anio_generacion) if anio_generacion else None
        anio_egreso = request.form.get('anio_egreso')
        alumno.anio_egreso = int(anio_egreso) if anio_egreso else None
        alumno.estatus = request.form.get('estatus', 'Activo') or 'Activo'
        carrera_id = request.form.get('carrera_id')
        alumno.carrera_id = int(carrera_id) if carrera_id else None
        db.session.commit()
        flash('Alumno actualizado.', 'success')
        return redirect(url_for('admin.alumnos'))
        
    carreras_list = active_query(Carrera).all()
    return render_template('admin/alumno_form.html', carreras=carreras_list, alumno=alumno)

@admin_bp.route('/alumnos/<int:id>/eliminar', methods=['POST'])
def eliminar_alumno(id):
    alumno = active_query(Alumno).filter_by(id=id).first_or_404()
    alumno.is_deleted = True
    # Cascade soft delete to expedientes and documents
    for exp in active_query(Expediente).filter_by(alumno_id=alumno.id).all():
        exp.is_deleted = True
        for doc in active_query(Documento).filter_by(expediente_id=exp.id).all():
            doc.is_deleted = True
    db.session.commit()
    flash('Alumno y sus expedientes eliminados.', 'success')
    return redirect(url_for('admin.alumnos'))

# --- IMPORTAR ---
@admin_bp.route('/importar', methods=['GET', 'POST'])
def importar():
    resultado = None
    tipo_modulo = 's'
    if request.method == 'POST':
        tipo_modulo = request.form.get('tipo_modulo', 's')
        if 'archivo_excel' not in request.files:
            flash('No se subió ningún archivo.', 'danger')
            return redirect(request.url)
            
        file = request.files['archivo_excel']
        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'danger')
            return redirect(request.url)
            
        if file and file.filename.endswith(('.xlsx', '.xls')):
            filepath = os.path.join('/tmp', secure_filename(file.filename))
            file.save(filepath)
            resultado = procesar_excel(filepath, tipo_modulo=tipo_modulo)
            os.remove(filepath)
            if resultado['errores']:
                flash('Importación completada con algunos errores. Revisa el resumen.', 'warning')
            else:
                flash('Importación masiva completada exitosamente.', 'success')
        else:
            flash('Formato de archivo no válido. Usa .xlsx o .xls', 'danger')
            
    return render_template('admin/importar.html', resultado=resultado, tipo_modulo=tipo_modulo)


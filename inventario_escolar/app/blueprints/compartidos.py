import os
from datetime import datetime, timezone
import pandas as pd
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import CarpetaCompartida, ArchivoCompartido
from app.decorators import active_query

compartidos_bp = Blueprint('compartidos', __name__)

@compartidos_bp.before_request
@login_required
def before_request():
    pass

@compartidos_bp.route('/')
def index():
    carpetas = active_query(CarpetaCompartida).order_by(CarpetaCompartida.nombre).all()
    return render_template('compartidos/index.html', carpetas=carpetas)

@compartidos_bp.route('/carpeta/crear', methods=['POST'])
def crear_carpeta():
    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')
    icono = request.form.get('icono', 'fa-folder')
    color = request.form.get('color', '#4f46e5')
    if nombre:
        nueva = CarpetaCompartida(
            nombre=nombre,
            descripcion=descripcion,
            icono=icono,
            color=color,
            created_by_id=current_user.id
        )
        db.session.add(nueva)
        db.session.commit()
        flash('Carpeta creada exitosamente.', 'success')
    return redirect(url_for('compartidos.index'))

@compartidos_bp.route('/carpeta/<int:carpeta_id>/editar', methods=['POST'])
def editar_carpeta(carpeta_id):
    carpeta_obj = active_query(CarpetaCompartida).filter_by(id=carpeta_id).first_or_404()
    if current_user.role.nombre != 'Super Admin' and carpeta_obj.created_by_id != current_user.id:
        flash('No tienes permiso para editar esta carpeta.', 'danger')
        return redirect(url_for('compartidos.index'))
    
    nombre = request.form.get('nombre')
    if not nombre:
        flash('El nombre es obligatorio.', 'danger')
        return redirect(url_for('compartidos.index'))
        
    carpeta_obj.nombre = nombre
    carpeta_obj.descripcion = request.form.get('descripcion')
    carpeta_obj.icono = request.form.get('icono', 'fa-folder')
    carpeta_obj.color = request.form.get('color', '#4f46e5')
    
    db.session.commit()
    flash('Carpeta actualizada exitosamente.', 'success')
    return redirect(url_for('compartidos.index'))

@compartidos_bp.route('/<int:carpeta_id>')
def carpeta(carpeta_id):
    carpeta_obj = active_query(CarpetaCompartida).filter_by(id=carpeta_id).first_or_404()
    archivos = active_query(ArchivoCompartido).filter_by(carpeta_id=carpeta_id).order_by(ArchivoCompartido.created_at.desc()).all()
    return render_template('compartidos/carpeta.html', carpeta=carpeta_obj, archivos=archivos)

@compartidos_bp.route('/<int:carpeta_id>/subir', methods=['POST'])
def subir_archivo(carpeta_id):
    carpeta_obj = active_query(CarpetaCompartida).filter_by(id=carpeta_id).first_or_404()
    archivo = request.files.get('archivo')
    nombre_personalizado = request.form.get('nombre')
    descripcion = request.form.get('descripcion')

    if not archivo or archivo.filename == '':
        flash('Debe seleccionar un archivo.', 'danger')
        return redirect(url_for('compartidos.carpeta', carpeta_id=carpeta_id))

    filename = secure_filename(archivo.filename)
    # Generate unique filename to avoid collisions
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    
    # Using 'compartidos' subfolder in UPLOAD_FOLDER
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'compartidos', str(carpeta_id))
    os.makedirs(upload_dir, exist_ok=True)
    
    ruta_absoluta = os.path.join(upload_dir, unique_filename)
    archivo.save(ruta_absoluta)

    ruta_relativa = os.path.join('compartidos', str(carpeta_id), unique_filename)
    
    # Extension for icon
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    nuevo_archivo = ArchivoCompartido(
        carpeta_id=carpeta_id,
        nombre=nombre_personalizado or filename,
        descripcion=descripcion,
        ruta_archivo=ruta_relativa,
        tipo_archivo=ext,
        uploaded_by_id=current_user.id
    )
    db.session.add(nuevo_archivo)
    db.session.commit()
    
    flash('Archivo subido exitosamente.', 'success')
    return redirect(url_for('compartidos.carpeta', carpeta_id=carpeta_id))

@compartidos_bp.route('/archivo/<int:archivo_id>/descargar')
def descargar_archivo(archivo_id):
    archivo = active_query(ArchivoCompartido).filter_by(id=archivo_id).first_or_404()
    if not archivo.ruta_archivo:
        abort(404)
        
    ruta_absoluta = os.path.join(current_app.config['UPLOAD_FOLDER'], archivo.ruta_archivo)
    if not os.path.exists(ruta_absoluta):
        flash('El archivo físico no se encontró en el servidor.', 'danger')
        return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))
        
    return send_file(ruta_absoluta, as_attachment=True, download_name=archivo.nombre + (f".{archivo.tipo_archivo}" if archivo.tipo_archivo and not archivo.nombre.endswith(f".{archivo.tipo_archivo}") else ""))

@compartidos_bp.route('/archivo/<int:archivo_id>/preview')
def preview_archivo(archivo_id):
    """Sirve el archivo inline (sin forzar descarga) para vista previa en el browser."""
    archivo = active_query(ArchivoCompartido).filter_by(id=archivo_id).first_or_404()
    if not archivo.ruta_archivo:
        abort(404)
        
    ruta_absoluta = os.path.join(current_app.config['UPLOAD_FOLDER'], archivo.ruta_archivo)
    if not os.path.exists(ruta_absoluta):
        flash('El archivo físico no se encontró en el servidor.', 'danger')
        return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))
        
    return send_file(ruta_absoluta, as_attachment=False)

@compartidos_bp.route('/carpeta/<int:carpeta_id>/eliminar', methods=['POST'])
def eliminar_carpeta(carpeta_id):
    carpeta_obj = active_query(CarpetaCompartida).filter_by(id=carpeta_id).first_or_404()
    # Permitir borrar solo si es admin o si el creador es el usuario actual
    if current_user.role.nombre != 'Super Admin' and carpeta_obj.created_by_id != current_user.id:
        flash('No tienes permiso para eliminar esta carpeta.', 'danger')
        return redirect(url_for('compartidos.index'))
        
    carpeta_obj.is_deleted = True
    db.session.commit()
    flash('Carpeta eliminada.', 'success')
    return redirect(url_for('compartidos.index'))

@compartidos_bp.route('/archivo/<int:archivo_id>/editar', methods=['POST'])
def editar_archivo(archivo_id):
    archivo = active_query(ArchivoCompartido).filter_by(id=archivo_id).first_or_404()
    if current_user.role.nombre != 'Super Admin' and archivo.uploaded_by_id != current_user.id:
        flash('No tienes permiso para editar este archivo.', 'danger')
        return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))

    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    
    if not nombre:
        flash('El nombre no puede estar vacío.', 'danger')
        return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))
        
    archivo.nombre = nombre
    archivo.descripcion = descripcion
    db.session.commit()
    flash('Archivo actualizado correctamente.', 'success')
    return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))

@compartidos_bp.route('/archivo/<int:archivo_id>/eliminar', methods=['POST'])
def eliminar_archivo(archivo_id):
    archivo = active_query(ArchivoCompartido).filter_by(id=archivo_id).first_or_404()
    # Permitir borrar solo si es admin o si el subidor es el usuario actual
    if current_user.role.nombre != 'Super Admin' and archivo.uploaded_by_id != current_user.id:
        flash('No tienes permiso para eliminar este archivo.', 'danger')
        return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))
        
    archivo.is_deleted = True
    db.session.commit()
    flash('Archivo eliminado.', 'success')
    return redirect(url_for('compartidos.carpeta', carpeta_id=archivo.carpeta_id))

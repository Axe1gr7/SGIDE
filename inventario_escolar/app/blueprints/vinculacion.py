import os
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, send_file, abort, jsonify)
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import ModuloVinculacion, SubModuloVinculacion, ArchivoSubModulo
from app.decorators import roles_required

vinculacion_bp = Blueprint('vinculacion', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'zip', 'txt'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _tipo_from_ext(filename):
    if '.' not in filename:
        return 'file'
    ext = filename.rsplit('.', 1)[1].lower()
    mapping = {
        'pdf': 'pdf', 'docx': 'word', 'doc': 'word',
        'xlsx': 'excel', 'xls': 'excel',
        'png': 'image', 'jpg': 'image', 'jpeg': 'image',
        'zip': 'zip', 'txt': 'text',
    }
    return mapping.get(ext, 'file')


def _save_file(archivo, submodulo_id):
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vinculacion', str(submodulo_id))
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(archivo.filename)
    path = os.path.join(upload_folder, filename)
    archivo.save(path)
    return os.path.join('vinculacion', str(submodulo_id), filename)


# ── Auth guard ───────────────────────────────────────────────────────────────

@vinculacion_bp.before_request
@login_required
@roles_required('Super Admin', 'Vinculacion')
def before_request():
    pass


# ── Módulos (vista principal) ────────────────────────────────────────────────

@vinculacion_bp.route('/')
def lista():
    modulos = (ModuloVinculacion.query
               .filter_by(is_deleted=False)
               .order_by(ModuloVinculacion.orden, ModuloVinculacion.nombre)
               .all())
    return render_template('vinculacion/lista.html', modulos=modulos)


@vinculacion_bp.route('/crear', methods=['POST'])
def crear_modulo():
    nombre      = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    icono       = request.form.get('icono', 'fa-folder').strip()
    color       = request.form.get('color', '#4f46e5').strip()

    if not nombre:
        flash('El nombre del módulo es requerido.', 'danger')
        return redirect(url_for('vinculacion.lista'))

    m = ModuloVinculacion(nombre=nombre, descripcion=descripcion, icono=icono, color=color)
    db.session.add(m)
    db.session.commit()
    flash(f'Módulo «{nombre}» creado correctamente.', 'success')
    return redirect(url_for('vinculacion.lista'))


@vinculacion_bp.route('/<int:id>/editar', methods=['POST'])
def editar_modulo(id):
    m = ModuloVinculacion.query.filter_by(id=id, is_deleted=False).first_or_404()
    m.nombre      = request.form.get('nombre', m.nombre).strip()
    m.descripcion = request.form.get('descripcion', '').strip()
    m.icono       = request.form.get('icono', m.icono).strip()
    m.color       = request.form.get('color', m.color).strip()
    db.session.commit()
    flash('Módulo actualizado.', 'success')
    return redirect(url_for('vinculacion.lista'))


@vinculacion_bp.route('/<int:id>/eliminar', methods=['POST'])
def eliminar_modulo(id):
    m = ModuloVinculacion.query.filter_by(id=id, is_deleted=False).first_or_404()
    m.is_deleted = True
    db.session.commit()
    flash('Módulo eliminado.', 'success')
    return redirect(url_for('vinculacion.lista'))


# ── Detalle de módulo (sub-módulos) ─────────────────────────────────────────

@vinculacion_bp.route('/<int:id>')
def detalle_modulo(id):
    modulo = ModuloVinculacion.query.filter_by(id=id, is_deleted=False).first_or_404()
    submodulos = (SubModuloVinculacion.query
                  .filter_by(modulo_id=id, is_deleted=False)
                  .order_by(SubModuloVinculacion.orden, SubModuloVinculacion.nombre)
                  .all())
    return render_template('vinculacion/detalle_modulo.html', modulo=modulo, submodulos=submodulos)


@vinculacion_bp.route('/<int:id>/submodulo/crear', methods=['POST'])
def crear_submodulo(id):
    modulo = ModuloVinculacion.query.filter_by(id=id, is_deleted=False).first_or_404()
    nombre      = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    icono       = request.form.get('icono', 'fa-folder-open').strip()

    if not nombre:
        flash('El nombre del sub-módulo es requerido.', 'danger')
        return redirect(url_for('vinculacion.detalle_modulo', id=id))

    s = SubModuloVinculacion(modulo_id=id, nombre=nombre, descripcion=descripcion, icono=icono)
    db.session.add(s)
    db.session.commit()
    flash(f'Sub-módulo «{nombre}» creado.', 'success')
    return redirect(url_for('vinculacion.detalle_modulo', id=id))


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/editar', methods=['POST'])
def editar_submodulo(id, sid):
    s = SubModuloVinculacion.query.filter_by(id=sid, modulo_id=id, is_deleted=False).first_or_404()
    s.nombre      = request.form.get('nombre', s.nombre).strip()
    s.descripcion = request.form.get('descripcion', '').strip()
    s.icono       = request.form.get('icono', s.icono).strip()
    db.session.commit()
    flash('Sub-módulo actualizado.', 'success')
    return redirect(url_for('vinculacion.detalle_modulo', id=id))


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/eliminar', methods=['POST'])
def eliminar_submodulo(id, sid):
    s = SubModuloVinculacion.query.filter_by(id=sid, modulo_id=id, is_deleted=False).first_or_404()
    s.is_deleted = True
    db.session.commit()
    flash('Sub-módulo eliminado.', 'success')
    return redirect(url_for('vinculacion.detalle_modulo', id=id))


# ── Detalle de sub-módulo (archivos) ─────────────────────────────────────────

@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>')
def detalle_submodulo(id, sid):
    modulo    = ModuloVinculacion.query.filter_by(id=id, is_deleted=False).first_or_404()
    submodulo = SubModuloVinculacion.query.filter_by(id=sid, modulo_id=id, is_deleted=False).first_or_404()
    archivos  = (ArchivoSubModulo.query
                 .filter_by(submodulo_id=sid, is_deleted=False)
                 .order_by(ArchivoSubModulo.nombre)
                 .all())
    return render_template('vinculacion/detalle_submodulo.html',
                           modulo=modulo, submodulo=submodulo, archivos=archivos)


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/archivo/subir', methods=['POST'])
def subir_archivo(id, sid):
    submodulo = SubModuloVinculacion.query.filter_by(id=sid, modulo_id=id, is_deleted=False).first_or_404()
    nombre      = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    archivo     = request.files.get('archivo')

    ruta_archivo = None
    tipo_archivo = 'file'

    if archivo and archivo.filename:
        if not _allowed(archivo.filename):
            flash('Tipo de archivo no permitido.', 'danger')
            return redirect(url_for('vinculacion.detalle_submodulo', id=id, sid=sid))
        ruta_archivo = _save_file(archivo, sid)
        tipo_archivo = _tipo_from_ext(archivo.filename)
        if not nombre:
            nombre = secure_filename(archivo.filename)

    if not nombre:
        flash('El nombre del archivo es requerido.', 'danger')
        return redirect(url_for('vinculacion.detalle_submodulo', id=id, sid=sid))

    a = ArchivoSubModulo(submodulo_id=sid, nombre=nombre, descripcion=descripcion,
                         ruta_archivo=ruta_archivo, tipo_archivo=tipo_archivo)
    db.session.add(a)
    db.session.commit()
    flash(f'Archivo «{nombre}» registrado.', 'success')
    return redirect(url_for('vinculacion.detalle_submodulo', id=id, sid=sid))


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/archivo/<int:aid>/editar', methods=['POST'])
def editar_archivo(id, sid, aid):
    a = ArchivoSubModulo.query.filter_by(id=aid, submodulo_id=sid, is_deleted=False).first_or_404()
    nombre      = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    if not nombre:
        flash('El nombre no puede estar vacío.', 'danger')
        return redirect(url_for('vinculacion.detalle_submodulo', id=id, sid=sid))
    a.nombre      = nombre
    a.descripcion = descripcion
    db.session.commit()
    flash('Archivo renombrado correctamente.', 'success')
    return redirect(url_for('vinculacion.detalle_submodulo', id=id, sid=sid))


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/archivo/<int:aid>/eliminar', methods=['POST'])
def eliminar_archivo(id, sid, aid):
    a = ArchivoSubModulo.query.filter_by(id=aid, submodulo_id=sid, is_deleted=False).first_or_404()
    a.is_deleted = True
    db.session.commit()
    flash('Archivo eliminado.', 'success')
    return redirect(url_for('vinculacion.detalle_submodulo', id=id, sid=sid))


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/archivo/<int:aid>/descargar')
def descargar_archivo(id, sid, aid):
    a = ArchivoSubModulo.query.filter_by(id=aid, submodulo_id=sid, is_deleted=False).first_or_404()
    if not a.ruta_archivo:
        abort(404)
    ruta_abs = os.path.join(current_app.config['UPLOAD_FOLDER'], a.ruta_archivo)
    if not os.path.exists(ruta_abs):
        abort(404)
    return send_file(ruta_abs, as_attachment=True, download_name=os.path.basename(a.ruta_archivo))


@vinculacion_bp.route('/<int:id>/submodulo/<int:sid>/archivo/<int:aid>/preview')
def preview_archivo(id, sid, aid):
    """Sirve el archivo inline (sin forzar descarga) para vista previa en el browser."""
    a = ArchivoSubModulo.query.filter_by(id=aid, submodulo_id=sid, is_deleted=False).first_or_404()
    if not a.ruta_archivo:
        abort(404)
    ruta_abs = os.path.join(current_app.config['UPLOAD_FOLDER'], a.ruta_archivo)
    if not os.path.exists(ruta_abs):
        abort(404)
    return send_file(ruta_abs, as_attachment=False)

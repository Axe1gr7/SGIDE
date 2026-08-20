import os
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, send_file, abort, jsonify)
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import ModuloVinculacion, SubModuloVinculacion, ArchivoSubModulo, Alumno, Universidad, Expediente, Documento, Carrera
from app.decorators import roles_required, active_query
from app.services.logic_word import generar_documento_word
from app.services.file_manager import guardar_documento, obtener_ruta_absoluta

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


# ── Inicio / Panel General ───────────────────────────────────────────────────

@vinculacion_bp.route('/')
def inicio():
    # Estadísticas
    total_alumnos = active_query(Alumno).count()
    
    # Aptos para estancia (con Servicio y Prácticas completados)
    alumnos_all = active_query(Alumno).all()
    total_aptos = sum(1 for a in alumnos_all if a.puede_realizar_estancia)
    
    # En estancia activa (con expediente 'v' y universidad asignada)
    total_estancias = (active_query(Expediente)
                       .filter(Expediente.tipo_modulo == 'v', 
                               Expediente.universidad_id != None)
                       .count())
    
    total_universidades = active_query(Universidad).count()
    
    stats = {
        'total_alumnos': total_alumnos,
        'total_aptos': total_aptos,
        'total_estancias': total_estancias,
        'total_universidades': total_universidades
    }
    
    return render_template('vinculacion/inicio.html', stats=stats)


# ── Módulos / Gestión de Documentos ──────────────────────────────────────────

@vinculacion_bp.route('/documentos')
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


# ── Catálogo de Universidades ───────────────────────────────────────────────

@vinculacion_bp.route('/universidades')
def universidades():
    unis = active_query(Universidad).order_by(Universidad.nombre).all()
    return render_template('vinculacion/universidades.html', universidades=unis)


@vinculacion_bp.route('/universidades/crear', methods=['POST'])
def crear_universidad():
    nombre = request.form.get('nombre', '').strip()
    domicilio = request.form.get('domicilio', '').strip()
    contacto = request.form.get('contacto', '').strip()
    telefono = request.form.get('telefono', '').strip()
    correo = request.form.get('correo', '').strip()

    if not nombre:
        flash('El nombre de la universidad es requerido.', 'danger')
        return redirect(url_for('vinculacion.universidades'))

    uni = Universidad(nombre=nombre, domicilio=domicilio, contacto=contacto, telefono=telefono, correo=correo)
    db.session.add(uni)
    db.session.commit()
    flash(f'Universidad «{nombre}» registrada correctamente.', 'success')
    return redirect(url_for('vinculacion.universidades'))


@vinculacion_bp.route('/universidades/<int:uid>/editar', methods=['POST'])
def editar_universidad(uid):
    uni = active_query(Universidad).filter_by(id=uid).first_or_404()
    uni.nombre = request.form.get('nombre', '').strip() or uni.nombre
    uni.domicilio = request.form.get('domicilio', '').strip()
    uni.contacto = request.form.get('contacto', '').strip()
    uni.telefono = request.form.get('telefono', '').strip()
    uni.correo = request.form.get('correo', '').strip()

    db.session.commit()
    flash('Universidad actualizada correctamente.', 'success')
    return redirect(url_for('vinculacion.universidades'))


@vinculacion_bp.route('/universidades/<int:uid>/eliminar', methods=['POST'])
def eliminar_universidad(uid):
    uni = active_query(Universidad).filter_by(id=uid).first_or_404()
    uni.is_deleted = True
    db.session.commit()
    flash('Universidad eliminada de la lista.', 'success')
    return redirect(url_for('vinculacion.universidades'))


# ── Consulta de Alumnos y Estancias ──────────────────────────────────────────

@vinculacion_bp.route('/alumnos')
def alumnos():
    search = request.args.get('search', '').strip()
    carrera_filter = request.args.get('carrera_filter')
    estatus_filter = request.args.get('estatus_filter')
    aptos_filter = request.args.get('aptos_filter') == '1'
    page = request.args.get('page', 1, type=int)

    query = active_query(Alumno)

    if search:
        query = query.filter((Alumno.nombre.ilike(f'%{search}%')) | (Alumno.matricula.ilike(f'%{search}%')))
    if carrera_filter:
        query = query.filter(Alumno.carrera_id == carrera_filter)
    if estatus_filter:
        query = query.filter(Alumno.estatus == estatus_filter)

    carreras = active_query(Carrera).all()
    unis = active_query(Universidad).order_by(Universidad.nombre).all()
    
    alumnos_list = query.all()
    
    if aptos_filter:
        alumnos_list = [a for a in alumnos_list if a.puede_realizar_estancia]
        
    per_page = 20
    total = len(alumnos_list)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_alumnos = alumnos_list[start:end]
    
    has_prev = page > 1
    has_next = end < total
    
    alumnos_data = []
    for a in paginated_alumnos:
        exp_v = a.expedientes.filter_by(tipo_modulo='v', is_deleted=False).first()
        alumnos_data.append({
            'alumno': a,
            'exp_v': exp_v,
            'is_apto': a.puede_realizar_estancia,
            'has_servicio': bool(a.servicio_completado),
            'has_practicas': bool(a.practicas_completado),
        })

    return render_template('vinculacion/alumnos.html',
                           alumnos=alumnos_data,
                           carreras=carreras,
                           universidades=unis,
                           search=search,
                           carrera_filter=carrera_filter,
                           estatus_filter=estatus_filter,
                           aptos_filter=aptos_filter,
                           page=page,
                           has_prev=has_prev,
                           has_next=has_next,
                           total_pages=(total + per_page - 1) // per_page)


@vinculacion_bp.route('/alumnos/asignar', methods=['POST'])
def asignar_estancia():
    alumno_id = request.form.get('alumno_id')
    universidad_id = request.form.get('universidad_id')
    periodo = request.form.get('periodo', '').strip()

    if not alumno_id:
        flash('Estudiante no válido.', 'danger')
        return redirect(url_for('vinculacion.alumnos'))

    alumno = active_query(Alumno).filter_by(id=alumno_id).first_or_404()

    if not alumno.puede_realizar_estancia:
        flash(f'El estudiante {alumno.nombre} no cumple con los requisitos (Servicio y Prácticas completados) para realizar estancias.', 'danger')
        return redirect(url_for('vinculacion.alumnos'))

    exp_v = alumno.expedientes.filter_by(tipo_modulo='v', is_deleted=False).first()
    if not exp_v:
        exp_v = Expediente(
            alumno_id=alumno.id,
            tipo_modulo='v',
            clave_expediente=f"v-{alumno.expediente_base}"
        )
        db.session.add(exp_v)
        db.session.flush()

    exp_v.universidad_id = int(universidad_id) if universidad_id else None
    exp_v.periodo = periodo or None
    db.session.commit()

    flash(f'Estancia asignada correctamente a {alumno.nombre}.', 'success')
    return redirect(url_for('vinculacion.alumnos'))


# ── Expediente Individual de Estancia ────────────────────────────────────────

@vinculacion_bp.route('/alumnos/expediente/<int:id>')
def expediente_detalle(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo='v').first_or_404()
    alumno = expediente.alumno
    documentos = active_query(Documento).filter_by(expediente_id=id).all()
    unis = active_query(Universidad).order_by(Universidad.nombre).all()
    
    return render_template('vinculacion/expediente_detalle.html',
                           expediente=expediente,
                           alumno=alumno,
                           documentos=documentos,
                           universidades=unis)


@vinculacion_bp.route('/alumnos/expediente/<int:id>/actualizar-universidad', methods=['POST'])
def actualizar_estancia_exp(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo='v').first_or_404()
    universidad_id = request.form.get('universidad_id')
    periodo = request.form.get('periodo', '').strip()

    expediente.universidad_id = int(universidad_id) if universidad_id else None
    expediente.periodo = periodo or None
    db.session.commit()

    flash('Asignación de universidad y periodo actualizada.', 'success')
    return redirect(url_for('vinculacion.expediente_detalle', id=id))


@vinculacion_bp.route('/alumnos/expediente/<int:id>/documento/crear', methods=['POST'])
def crear_documento_estancia(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo='v').first_or_404()
    nombre_formato = request.form.get('nombre_formato')
    estado = request.form.get('estado', 'Pendiente')
    observaciones = request.form.get('observaciones', '')
    archivo = request.files.get('archivo')

    if not nombre_formato:
        flash('El nombre del documento es requerido.', 'danger')
        return redirect(url_for('vinculacion.expediente_detalle', id=id))

    ruta_archivo = None
    if archivo and archivo.filename:
        ruta_archivo = guardar_documento(expediente, archivo)

    doc = Documento(expediente_id=id, nombre_formato=nombre_formato, estado=estado, observaciones=observaciones, ruta_archivo=ruta_archivo)
    db.session.add(doc)
    db.session.commit()
    
    flash('Documento agregado al expediente.', 'success')
    return redirect(url_for('vinculacion.expediente_detalle', id=id))


@vinculacion_bp.route('/alumnos/expediente/<int:id>/documento/<int:doc_id>/editar', methods=['POST'])
def editar_documento_estancia(id, doc_id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo='v').first_or_404()
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()

    doc.nombre_formato = request.form.get('nombre_formato')
    doc.estado = request.form.get('estado')
    doc.observaciones = request.form.get('observaciones')
    archivo = request.files.get('archivo')

    if archivo and archivo.filename:
        doc.ruta_archivo = guardar_documento(expediente, archivo)

    db.session.commit()
    flash('Documento actualizado correctamente.', 'success')
    return redirect(url_for('vinculacion.expediente_detalle', id=id))


@vinculacion_bp.route('/alumnos/expediente/<int:id>/documento/<int:doc_id>/eliminar', methods=['POST'])
def eliminar_documento_estancia(id, doc_id):
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    doc.is_deleted = True
    db.session.commit()
    flash('Documento eliminado.', 'success')
    return redirect(url_for('vinculacion.expediente_detalle', id=id))


@vinculacion_bp.route('/alumnos/expediente/<int:id>/documento/<int:doc_id>/descargar')
def descargar_archivo_estancia(id, doc_id):
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    if not doc.ruta_archivo:
        abort(404)
    ruta_absoluta = obtener_ruta_absoluta(doc.ruta_archivo)
    if not ruta_absoluta or not os.path.exists(ruta_absoluta):
        abort(404)
    return send_file(ruta_absoluta, as_attachment=True, download_name=os.path.basename(doc.ruta_archivo))


@vinculacion_bp.route('/alumnos/expediente/<int:id>/generar-word', methods=['POST'])
def generar_word_estancia(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo='v').first_or_404()
    try:
        output_path, filename = generar_documento_word(expediente.alumno_id, 'v')
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el documento: {str(e)}', 'danger')
        return redirect(url_for('vinculacion.expediente_detalle', id=id))

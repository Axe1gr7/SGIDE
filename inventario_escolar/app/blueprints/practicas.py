import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Expediente, Documento, Carrera, Alumno, Dependencia
from app.decorators import roles_required, active_query
from app.services.logic_word import generar_documento_word
from app.services.file_manager import guardar_documento, obtener_ruta_absoluta
from app.services.logic_excel import procesar_excel
from app.services.logic_zip import procesar_zip_pdfs

practicas_bp = Blueprint('practicas', __name__)

MODULO_TIPO = 'p'
MODULO_LABEL = 'Prácticas Profesionales'
MODULO_PREFIX = 'practicas'

ESTATUSES = ['Activo', 'Inactivo', 'Egresado']

@practicas_bp.before_request
@login_required
@roles_required('Super Admin', 'Practicas')
def before_request():
    pass

@practicas_bp.route('/')
def lista():
    page = request.args.get('page', 1, type=int)
    carrera_filter = request.args.get('carrera_filter')
    search = request.args.get('search')
    estado_filter = request.args.get('estado_filter')
    estatus_filter = request.args.get('estatus_filter')

    query = active_query(Expediente).filter_by(tipo_modulo=MODULO_TIPO).join(Alumno)

    if carrera_filter:
        query = query.filter(Alumno.carrera_id == carrera_filter)
    if search:
        query = query.filter((Alumno.nombre.ilike(f'%{search}%')) | (Alumno.matricula.ilike(f'%{search}%')))
    if estado_filter:
        query = query.join(Documento).filter(Documento.estado == estado_filter).distinct()
    if estatus_filter:
        query = query.filter(Alumno.estatus == estatus_filter)

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    carreras = active_query(Carrera).all()

    return render_template('expedientes/lista.html',
                           pagination=pagination,
                           carreras=carreras,
                           carrera_filter=carrera_filter,
                           search=search,
                           estado_filter=estado_filter,
                           estatus_filter=estatus_filter,
                           estatuses=ESTATUSES,
                           es_practicas=True,
                           modulo_label=MODULO_LABEL,
                           modulo_tipo=MODULO_TIPO,
                           modulo_prefix=MODULO_PREFIX)

@practicas_bp.route('/<int:id>')
def detalle(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    documentos = active_query(Documento).filter_by(expediente_id=id).all()
    dependencias = active_query(Dependencia).filter(
        db.func.lower(Dependencia.tipo).in_(['practicas', 'ambos'])
    ).order_by(Dependencia.nombre).all()
    return render_template('expedientes/detalle.html',
                           expediente=expediente,
                           alumno=expediente.alumno,
                           documentos=documentos,
                           dependencias=dependencias,
                           es_practicas=True,
                           modulo_label=MODULO_LABEL,
                           modulo_tipo=MODULO_TIPO,
                           modulo_prefix=MODULO_PREFIX)


@practicas_bp.route('/<int:id>/dependencia', methods=['POST'])
def actualizar_dependencia(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    dep_id = request.form.get('dependencia_id')
    if dep_id:
        dependencia = active_query(Dependencia).filter_by(id=int(dep_id)).first()
        if dependencia:
            expediente.dependencia_id = dependencia.id
            db.session.commit()
            flash('Dependencia asignada.', 'success')
        else:
            flash('Dependencia no encontrada.', 'danger')
    else:
        expediente.dependencia_id = None
        db.session.commit()
        flash('Dependencia desasignada.', 'info')
    return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@practicas_bp.route('/<int:id>/documento/crear', methods=['GET', 'POST'])
def crear_documento(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    if request.method == 'POST':
        nombre_formato = request.form.get('nombre_formato')
        estado = request.form.get('estado')
        observaciones = request.form.get('observaciones')
        archivo = request.files.get('archivo')

        ruta_archivo = None
        if archivo and archivo.filename:
            ruta_archivo = guardar_documento(expediente, archivo)

        doc = Documento(expediente_id=id, nombre_formato=nombre_formato, estado=estado, observaciones=observaciones, ruta_archivo=ruta_archivo)
        db.session.add(doc)
        db.session.commit()
        flash('Documento agregado.', 'success')
        return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

    return render_template('expedientes/documento_form.html',
                           expediente=expediente,
                           documento=None,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX,
                           form_action=url_for(f'{MODULO_PREFIX}.crear_documento', id=id))

@practicas_bp.route('/<int:id>/documento/<int:doc_id>/editar', methods=['GET', 'POST'])
def editar_documento(id, doc_id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()

    if request.method == 'POST':
        doc.nombre_formato = request.form.get('nombre_formato')
        doc.estado = request.form.get('estado')
        doc.observaciones = request.form.get('observaciones')
        archivo = request.files.get('archivo')

        if archivo and archivo.filename:
            doc.ruta_archivo = guardar_documento(expediente, archivo)

        db.session.commit()
        flash('Documento actualizado.', 'success')
        return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

    return render_template('expedientes/documento_form.html',
                           expediente=expediente,
                           documento=doc,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX,
                           form_action=url_for(f'{MODULO_PREFIX}.editar_documento', id=id, doc_id=doc.id))

@practicas_bp.route('/<int:id>/documento/<int:doc_id>/eliminar', methods=['POST'])
def eliminar_documento(id, doc_id):
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    doc.is_deleted = True
    db.session.commit()
    flash('Documento eliminado.', 'success')
    return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@practicas_bp.route('/<int:id>/documento/<int:doc_id>/descargar')
def descargar_archivo(id, doc_id):
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    if not doc.ruta_archivo:
        abort(404)
    ruta_absoluta = obtener_ruta_absoluta(doc.ruta_archivo)
    if not ruta_absoluta or not os.path.exists(ruta_absoluta):
        abort(404)
    return send_file(ruta_absoluta, as_attachment=True, download_name=os.path.basename(doc.ruta_archivo))

@practicas_bp.route('/<int:id>/generar-word', methods=['POST'])
def generar_word(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    try:
        output_path, filename = generar_documento_word(expediente.alumno_id, MODULO_TIPO)
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el documento: {str(e)}', 'danger')
        return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@practicas_bp.route('/importar', methods=['GET', 'POST'])
def importar():
    resultado = None
    resultado_zip = None
    if request.method == 'POST':
        file_excel = request.files.get('archivo_excel')
        file_zip   = request.files.get('archivo_zip')

        if (not file_excel or file_excel.filename == '') and (not file_zip or file_zip.filename == ''):
            flash('Debes subir al menos un archivo Excel o un ZIP de PDFs.', 'danger')
            return redirect(request.url)

        # Procesar Excel
        if file_excel and file_excel.filename and file_excel.filename.endswith(('.xlsx', '.xls')):
            filepath = os.path.join('/tmp', secure_filename(file_excel.filename))
            file_excel.save(filepath)
            resultado = procesar_excel(filepath, tipo_modulo=MODULO_TIPO)
            os.remove(filepath)
            if resultado['errores']:
                flash('Importación Excel completada con algunos errores.', 'warning')
            else:
                flash('Importación masiva Excel completada exitosamente.', 'success')

        # Procesar ZIP de PDFs
        if file_zip and file_zip.filename and file_zip.filename.lower().endswith('.zip'):
            resultado_zip = procesar_zip_pdfs(file_zip, tipo_modulo=MODULO_TIPO)
            if resultado_zip['errores']:
                flash(f'ZIP procesado con {resultado_zip["no_asignados"]} PDFs no asignados. Revisa el resumen.', 'warning')
            else:
                flash(f'ZIP procesado: {resultado_zip["asignados"]} PDFs asignados correctamente.', 'success')

    return render_template('expedientes/importar.html',
                           resultado=resultado,
                           resultado_zip=resultado_zip,
                           modulo_label=MODULO_LABEL,
                           modulo_tipo=MODULO_TIPO,
                           modulo_prefix=MODULO_PREFIX)


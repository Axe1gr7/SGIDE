import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Expediente, Documento, Carrera, Alumno, Dependencia
from app.decorators import roles_required, active_query
from app.services.logic_word import generar_documento_pdf, generar_documento_word
from app.services.file_manager import guardar_documento, obtener_ruta_absoluta
from app.services.logic_excel import procesar_excel
from app.services.logic_zip import procesar_zip_pdfs
from app.models import CarpetaCompartida, ArchivoCompartido

servicio_bp = Blueprint('servicio', __name__)

MODULO_TIPO = 's'
MODULO_LABEL = 'Servicio Social'
MODULO_PREFIX = 'servicio'

SECTORES = ['Municipal', 'Estatal', 'Salud']

@servicio_bp.before_request
@login_required
@roles_required('Super Admin', 'Servicio')
def before_request():
    pass

@servicio_bp.route('/')
@servicio_bp.route('/menu')
def menu():
    total_alumnos = active_query(Alumno).count()
    total_expedientes = active_query(Expediente).filter_by(tipo_modulo=MODULO_TIPO).count()
    servicio_finalizado = active_query(Alumno).filter_by(estatus='Servicio Finalizado').count()
    total_dependencias = active_query(Dependencia).filter(
        Dependencia.tipo.in_(['Servicio', 'Ambos'])
    ).count()

    stats = {
        'total_alumnos': total_alumnos,
        'total_expedientes': total_expedientes,
        'servicio_finalizado': servicio_finalizado,
        'total_dependencias': total_dependencias
    }

    return render_template('servicio/menu.html',
                           stats=stats,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)

@servicio_bp.route('/plantillas')
def plantillas():
    return redirect(url_for('plantillas.lista', modulo='s'))

@servicio_bp.route('/dashboard')
def dashboard():
    expedientes = active_query(Expediente).filter_by(tipo_modulo=MODULO_TIPO).all()
    total_expedientes = len(expedientes)

    completados = 0
    en_tramite = 0
    pendientes = 0

    for exp in expedientes:
        docs = active_query(Documento).filter_by(expediente_id=exp.id).all()
        fss8 = next((d for d in docs if 'FSS8' in (d.nombre_formato or '') or 'terminacion' in (d.nombre_formato or '').lower()), None)
        has_entregados = any(d.estado == 'Entregado' for d in docs)

        if (fss8 and fss8.estado == 'Entregado') or (exp.alumno and exp.alumno.estatus == 'Servicio Finalizado'):
            completados += 1
        elif has_entregados:
            en_tramite += 1
        else:
            pendientes += 1

    # Conteo por sector
    sector_counts = {}
    for sec in SECTORES:
        sector_counts[sec] = sum(1 for exp in expedientes if exp.sector == sec)
    sector_counts['Sin asignar'] = sum(1 for exp in expedientes if not exp.sector or exp.sector not in SECTORES)

    # Conteo por carrera
    carreras = active_query(Carrera).all()
    carrera_data = {c.nombre: 0 for c in carreras}
    for exp in expedientes:
        if exp.alumno and exp.alumno.carrera:
            nombre_carrera = exp.alumno.carrera.nombre
            carrera_data[nombre_carrera] = carrera_data.get(nombre_carrera, 0) + 1

    return render_template('servicio/dashboard.html',
                           total_expedientes=total_expedientes,
                           completados=completados,
                           en_tramite=en_tramite,
                           pendientes=pendientes,
                           sector_data=sector_counts,
                           carrera_data=carrera_data,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)

@servicio_bp.route('/alumnos')
def alumnos():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    carrera_filter = request.args.get('carrera_filter', '')
    estatus_filter = request.args.get('estatus_filter', '')
    solo_aptos = request.args.get('solo_aptos', '')

    query = active_query(Alumno)

    if search:
        query = query.filter((Alumno.nombre.ilike(f'%{search}%')) | (Alumno.matricula.ilike(f'%{search}%')))
    if carrera_filter:
        query = query.filter(Alumno.carrera_id == carrera_filter)
    if estatus_filter:
        query = query.filter(Alumno.estatus == estatus_filter)

    all_alumnos = query.all()
    alumnos_data = []

    for a in all_alumnos:
        exp = active_query(Expediente).filter_by(alumno_id=a.id, tipo_modulo=MODULO_TIPO).first()
        is_finalizado = a.estatus == 'Servicio Finalizado' or (exp and any('FSS8' in (d.nombre_formato or '') and d.estado == 'Entregado' for d in exp.documentos))
        has_expediente = exp is not None

        if solo_aptos and is_finalizado:
            continue

        alumnos_data.append({
            'alumno': a,
            'expediente': exp,
            'has_expediente': has_expediente,
            'is_finalizado': is_finalizado,
            'dependencia': exp.dependencia if exp else None
        })

    total = len(alumnos_data)
    per_page = 20
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    paginated_alumnos = alumnos_data[start:end]

    carreras = active_query(Carrera).all()
    estatuses = ['Activo', 'Inactivo', 'Servicio Finalizado', 'Egresado']
    dependencias = active_query(Dependencia).filter(Dependencia.tipo.in_(['Servicio', 'Ambos'])).all()
    carpetas_compartidas = active_query(CarpetaCompartida).all()

    return render_template('servicio/alumnos.html',
                           alumnos_data=paginated_alumnos,
                           page=page,
                           total_pages=total_pages,
                           has_prev=(page > 1),
                           has_next=(page < total_pages),
                           search=search,
                           carrera_filter=carrera_filter,
                           estatus_filter=estatus_filter,
                           solo_aptos=solo_aptos,
                           carreras=carreras,
                           estatuses=estatuses,
                           dependencias=dependencias,
                           carpetas_compartidas=carpetas_compartidas,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)

@servicio_bp.route('/expedientes')
@servicio_bp.route('/lista')
def lista():
    page = request.args.get('page', 1, type=int)
    carrera_filter = request.args.get('carrera_filter')
    search = request.args.get('search')
    estado_filter = request.args.get('estado_filter')
    sector_filter = request.args.get('sector_filter')

    query = active_query(Expediente).filter_by(tipo_modulo=MODULO_TIPO).join(Alumno)

    if carrera_filter:
        query = query.filter(Alumno.carrera_id == carrera_filter)
    if search:
        query = query.filter((Alumno.nombre.ilike(f'%{search}%')) | (Alumno.matricula.ilike(f'%{search}%')))
    if estado_filter:
        query = query.join(Documento).filter(Documento.estado == estado_filter).distinct()
    if sector_filter:
        query = query.filter(Expediente.sector == sector_filter)

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    carreras = active_query(Carrera).all()

    return render_template('servicio/lista.html',
                           pagination=pagination,
                           carreras=carreras,
                           carrera_filter=carrera_filter,
                           search=search,
                           estado_filter=estado_filter,
                           sector_filter=sector_filter,
                           sectores=SECTORES,
                           es_servicio=True,
                           modulo_label=MODULO_LABEL,
                           modulo_tipo=MODULO_TIPO,
                           modulo_prefix=MODULO_PREFIX)

@servicio_bp.route('/exportar-compartidos', methods=['POST'])
def exportar_compartidos():
    import pandas as pd
    from datetime import datetime
    
    carpeta_id = request.form.get('carpeta_id')
    nueva_carpeta = request.form.get('nueva_carpeta')
    nombre_archivo = request.form.get('nombre_archivo', 'Reporte_Servicio')
    
    if nueva_carpeta:
        carpeta = CarpetaCompartida(nombre=nueva_carpeta, created_by_id=current_user.id)
        db.session.add(carpeta)
        db.session.commit()
        carpeta_id = carpeta.id
    elif carpeta_id:
        carpeta = active_query(CarpetaCompartida).filter_by(id=carpeta_id).first_or_404()
    else:
        flash('Debe seleccionar o crear una carpeta.', 'danger')
        return redirect(url_for(f'{MODULO_PREFIX}.lista'))

    carrera_filter = request.form.get('carrera_filter')
    search = request.form.get('search')
    estado_filter = request.form.get('estado_filter')
    sector_filter = request.form.get('sector_filter')

    query = active_query(Expediente).filter_by(tipo_modulo=MODULO_TIPO).join(Alumno)
    if carrera_filter: query = query.filter(Alumno.carrera_id == carrera_filter)
    if search: query = query.filter((Alumno.nombre.ilike(f'%{search}%')) | (Alumno.matricula.ilike(f'%{search}%')))
    if estado_filter: query = query.join(Documento).filter(Documento.estado == estado_filter).distinct()
    if sector_filter: query = query.filter(Expediente.sector == sector_filter)

    data = []
    for e in query.all():
        data.append({
            'Clave Expediente': e.clave_expediente,
            'Alumno': e.alumno.nombre,
            'Matrícula': e.alumno.matricula,
            'Carrera': e.alumno.carrera.nombre if e.alumno.carrera else '',
            'Generación': e.alumno.generacion_completa,
            'Estatus': e.alumno.estatus,
            'Sector': e.sector or '-',
            'Total Docs': e.documentos.filter_by(is_deleted=False).count(),
            'Docs Entregados': e.documentos.filter_by(is_deleted=False, estado='Entregado').count()
        })
        
    df = pd.DataFrame(data)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{nombre_archivo}_{timestamp}.xlsx"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'compartidos', str(carpeta_id))
    os.makedirs(upload_dir, exist_ok=True)
    ruta_absoluta = os.path.join(upload_dir, filename)
    
    df.to_excel(ruta_absoluta, index=False)
    
    ruta_relativa = os.path.join('compartidos', str(carpeta_id), filename)
    
    nuevo_archivo = ArchivoCompartido(
        carpeta_id=carpeta_id,
        nombre=nombre_archivo,
        ruta_archivo=ruta_relativa,
        tipo_archivo='xlsx',
        uploaded_by_id=current_user.id
    )
    db.session.add(nuevo_archivo)
    db.session.commit()
    
    flash(f'Reporte guardado en Compartidos -> {carpeta.nombre}', 'success')
    return redirect(url_for(f'{MODULO_PREFIX}.lista'))

@servicio_bp.route('/<int:id>')
def detalle(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    documentos = active_query(Documento).filter_by(expediente_id=id).all()
    dependencias = active_query(Dependencia).filter(
        db.func.lower(Dependencia.tipo).in_(['servicio', 'ambos'])
    ).order_by(Dependencia.nombre).all()
    return render_template('expedientes/detalle.html',
                           expediente=expediente,
                           alumno=expediente.alumno,
                           documentos=documentos,
                           sectores=SECTORES,
                           dependencias=dependencias,
                           es_servicio=True,
                           modulo_label=MODULO_LABEL,
                           modulo_tipo=MODULO_TIPO,
                           modulo_prefix=MODULO_PREFIX)

@servicio_bp.route('/<int:id>/sector', methods=['POST'])
def actualizar_sector(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    sector = request.form.get('sector')
    if sector in SECTORES:
        expediente.sector = sector
        db.session.commit()
        flash('Sector actualizado.', 'success')
    else:
        flash('Sector no válido.', 'danger')
    return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))


@servicio_bp.route('/<int:id>/dependencia', methods=['POST'])
def actualizar_dependencia(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    dep_id = request.form.get('dependencia_id')
    if dep_id:
        dependencia = active_query(Dependencia).filter_by(id=int(dep_id)).first()
        if dependencia:
            expediente.dependencia_id = dependencia.id
            # Autocompletar sector desde la dependencia
            if dependencia.sector:
                expediente.sector = dependencia.sector
            else:
                expediente.sector = None
                
            # Autogenerar documentos
            documentos_auto = ['FSS2 carta de presentacion', 'FSS4 Carta de aceptacion', 'FSS8 Constancia terminacion de ss']
            for doc_nombre in documentos_auto:
                existe = active_query(Documento).filter_by(expediente_id=id, nombre_formato=doc_nombre).first()
                if not existe:
                    nuevo_doc = Documento(expediente_id=id, nombre_formato=doc_nombre, estado='Pendiente')
                    db.session.add(nuevo_doc)
            
            db.session.commit()
            flash('Dependencia asignada y documentos inicializados.', 'success')
        else:
            flash('Dependencia no encontrada.', 'danger')
    else:
        expediente.dependencia_id = None
        db.session.commit()
        flash('Dependencia desasignada.', 'info')
    return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@servicio_bp.route('/<int:id>/documento/crear', methods=['GET', 'POST'])
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
            estado = 'Entregado'

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

@servicio_bp.route('/<int:id>/documento/<int:doc_id>/editar', methods=['GET', 'POST'])
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
            doc.estado = 'Entregado'

        # Actualizar estatus del alumno si es la constancia final
        if doc.nombre_formato == 'FSS8 Constancia terminacion de ss' and doc.estado == 'Entregado':
            if expediente.alumno:
                expediente.alumno.estatus = 'Servicio Finalizado'

        db.session.commit()
        flash('Documento actualizado.', 'success')
        return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

    return render_template('expedientes/documento_form.html',
                           expediente=expediente,
                           documento=doc,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX,
                           form_action=url_for(f'{MODULO_PREFIX}.editar_documento', id=id, doc_id=doc.id))

@servicio_bp.route('/<int:id>/documento/<int:doc_id>/eliminar', methods=['POST'])
def eliminar_documento(id, doc_id):
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    doc.is_deleted = True
    db.session.commit()
    flash('Documento eliminado.', 'success')
    return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@servicio_bp.route('/<int:id>/documento/<int:doc_id>/descargar')
def descargar_archivo(id, doc_id):
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    if not doc.ruta_archivo:
        abort(404)
    ruta_absoluta = obtener_ruta_absoluta(doc.ruta_archivo)
    if not ruta_absoluta or not os.path.exists(ruta_absoluta):
        abort(404)
    return send_file(ruta_absoluta, as_attachment=True, download_name=os.path.basename(doc.ruta_archivo))

@servicio_bp.route('/<int:id>/generar-word', methods=['POST'])
def generar_word(id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    try:
        output_path, filename = generar_documento_word(expediente.alumno_id, MODULO_TIPO)
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el documento: {str(e)}', 'danger')
        return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@servicio_bp.route('/<int:id>/documento/<int:doc_id>/generar-word', methods=['POST'])
def generar_word_documento(id, doc_id):
    expediente = active_query(Expediente).filter_by(id=id, tipo_modulo=MODULO_TIPO).first_or_404()
    doc = active_query(Documento).filter_by(id=doc_id, expediente_id=id).first_or_404()
    
    template_name = f"{doc.nombre_formato}.docx"
    
    try:
        output_path, filename = generar_documento_pdf(expediente.alumno_id, MODULO_TIPO, template_name=template_name)
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el formato {doc.nombre_formato}: {str(e)}', 'danger')
        return redirect(url_for(f'{MODULO_PREFIX}.detalle', id=id))

@servicio_bp.route('/importar', methods=['GET', 'POST'])
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

    return render_template('servicio/importar.html',
                           resultado=resultado,
                           resultado_zip=resultado_zip,
                           modulo_label=MODULO_LABEL,
                           modulo_tipo=MODULO_TIPO,
                           modulo_prefix=MODULO_PREFIX)


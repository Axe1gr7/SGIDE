import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.decorators import roles_required
from app.models import Alumno, Expediente
from app.services.logic_word import generar_documento_word, generar_documento_pdf
from app.decorators import active_query

plantillas_bp = Blueprint('plantillas', __name__)

PLANTILLAS_BASE = {
    'p': {'filename': 'plantilla_practicas.docx', 'label': 'Plantilla Base Prácticas Profesionales'},
    's': {'filename': 'plantilla_servicio.docx', 'label': 'Plantilla Base Servicio Social'},
    'v': {'filename': 'plantilla_vinculacion.docx', 'label': 'Plantilla Base Vinculación'},
}

TIPO_PLANTILLA_PRACTICAS = 'acreditacion_pp'
NOMBRE_PLANTILLA_PRACTICAS = 'Formato Constancia de Acreditacion PP'


def _carpetas_plantillas():
    """Devuelve las fuentes de plantillas en orden de prioridad."""
    templates_dir = current_app.config['TEMPLATES_WORD_FOLDER']
    project_root = os.path.dirname(current_app.root_path)
    return (
        ('templates_word', templates_dir),
        ('machotes', os.path.join(project_root, 'machotes')),
    )


def _archivos_plantillas():
    """Combina plantillas administrables y machotes sin duplicarlas por nombre."""
    archivos = {}
    for source, carpeta in _carpetas_plantillas():
        if not os.path.isdir(carpeta):
            continue
        for filename in os.listdir(carpeta):
            if filename.lower().endswith('.docx') and filename not in archivos:
                archivos[filename] = {
                    'filename': filename,
                    'path': os.path.join(carpeta, filename),
                    'source': source,
                }
    return sorted(archivos.values(), key=lambda item: item['filename'].lower())


def _buscar_archivo_plantilla(filename):
    safe_filename = secure_filename(filename)
    for item in _archivos_plantillas():
        if item['filename'] == safe_filename:
            return item
    return None


@plantillas_bp.before_request
@login_required
@roles_required('Super Admin', 'Practicas', 'Servicio', 'Vinculacion')
def before_request():
    pass


@plantillas_bp.route('/')
def lista():
    modulo_filter = request.args.get('modulo', '')
    target_dir = current_app.config['TEMPLATES_WORD_FOLDER']
    os.makedirs(target_dir, exist_ok=True)

    plantillas_data = []
    for archivo in _archivos_plantillas():
        f = archivo['filename']
        path = archivo['path']
        stat = os.stat(path)
        
        # Categorizar por módulo según prefijo o base
        mod_type = 'general'
        nombre_normalizado = f.lower()
        if (
            'practica' in nombre_normalizado
            or 'acreditacion' in nombre_normalizado
            or f.startswith('p_')
        ):
            mod_type = 'p'
        elif 'servicio' in nombre_normalizado or nombre_normalizado.startswith('fss') or f.startswith('s_'):
            mod_type = 's'
        elif 'vinculacion' in nombre_normalizado or f.startswith('v_'):
            mod_type = 'v'

        if modulo_filter and modulo_filter != mod_type and mod_type != 'general':
            continue

        plantillas_data.append({
            'filename': f,
            'name': f.replace('.docx', '').replace('_', ' ').title(),
            'mod_type': mod_type,
            'size_kb': round(stat.st_size / 1024, 1),
            'mtime': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
            'is_base': any(info['filename'] == f for info in PLANTILLAS_BASE.values())
                or archivo['source'] == 'machotes',
            'source': archivo['source'],
        })

    alumnos = active_query(Alumno).order_by(Alumno.nombre).all()

    return render_template('plantillas/gestion.html',
                           plantillas=plantillas_data,
                           alumnos=alumnos,
                           modulo_filter=modulo_filter)


@plantillas_bp.route('/subir', methods=['POST'])
def subir():
    file = request.files.get('plantilla')
    nombre_custom = request.form.get('nombre_custom', '').strip()
    modulo_dest = request.form.get('modulo_dest', 'p')
    tipo_plantilla = request.form.get('tipo_plantilla', '')

    if modulo_dest not in {'p', 's', 'v'}:
        flash('El módulo seleccionado no es válido.', 'danger')
        return redirect(url_for('plantillas.lista'))

    if modulo_dest == 'p':
        if tipo_plantilla != TIPO_PLANTILLA_PRACTICAS:
            flash('Selecciona el tipo de plantilla de Prácticas Profesionales.', 'danger')
            return redirect(url_for('plantillas.lista', modulo='p'))
        nombre_base = nombre_custom or NOMBRE_PLANTILLA_PRACTICAS
    else:
        nombre_base = nombre_custom

    if not file or file.filename == '':
        flash('Debes seleccionar un archivo Word (.docx).', 'danger')
        return redirect(url_for('plantillas.lista', modulo=modulo_dest))

    if not file.filename.lower().endswith('.docx'):
        flash('El archivo debe tener extensión .docx', 'danger')
        return redirect(url_for('plantillas.lista', modulo=modulo_dest))

    target_dir = current_app.config['TEMPLATES_WORD_FOLDER']
    os.makedirs(target_dir, exist_ok=True)

    if nombre_base:
        safe_name = secure_filename(nombre_base.replace(' ', '_'))
        if not safe_name.lower().endswith('.docx'):
            safe_name += '.docx'
        filename = f"{modulo_dest}_{safe_name}"
    else:
        filename = f"{modulo_dest}_{secure_filename(file.filename)}"

    target_path = os.path.join(target_dir, filename)
    file.save(target_path)
    flash(f'Plantilla "{filename}" subida exitosamente.', 'success')
    return redirect(url_for('plantillas.lista', modulo=modulo_dest))


@plantillas_bp.route('/descargar/<filename>')
def descargar(filename):
    archivo = _buscar_archivo_plantilla(filename)
    if not archivo:
        abort(404)
    return send_file(archivo['path'], as_attachment=True, download_name=archivo['filename'])


@plantillas_bp.route('/eliminar/<filename>', methods=['POST'])
def eliminar(filename):
    target_dir = current_app.config['TEMPLATES_WORD_FOLDER']
    safe_file = secure_filename(filename)
    path = os.path.join(target_dir, safe_file)
    if os.path.exists(path):
        os.remove(path)
        flash(f'Plantilla "{safe_file}" eliminada.', 'info')
    else:
        flash('Plantilla no encontrada.', 'warning')
    return redirect(url_for('plantillas.lista'))


@plantillas_bp.route('/generar', methods=['POST'])
def generar():
    alumno_id = request.form.get('alumno_id', type=int)
    template_name = request.form.get('template_name')
    tipo_modulo = request.form.get('tipo_modulo', 'p')
    formato = request.form.get('formato', 'docx')

    if not alumno_id or not template_name:
        flash('Debes seleccionar un alumno y una plantilla.', 'danger')
        return redirect(url_for('plantillas.lista', modulo=tipo_modulo))

    try:
        if formato == 'pdf':
            file_path, download_name = generar_documento_pdf(alumno_id, tipo_modulo, template_name=template_name)
        else:
            file_path, download_name = generar_documento_word(alumno_id, tipo_modulo, template_name=template_name)

        return send_file(file_path, as_attachment=True, download_name=download_name)
    except Exception as e:
        flash(f'Error al generar documento: {str(e)}', 'danger')
        return redirect(url_for('plantillas.lista', modulo=tipo_modulo))

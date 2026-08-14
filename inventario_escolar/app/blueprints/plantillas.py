import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.decorators import roles_required

plantillas_bp = Blueprint('plantillas', __name__)

# Mapa de plantillas soportadas
PLANTILLAS = {
    'p': {'filename': 'plantilla_practicas.docx', 'label': 'Prácticas Profesionales'},
    's': {'filename': 'plantilla_servicio.docx', 'label': 'Servicio Social (constancias)'},
    'v': {'filename': 'plantilla_vinculacion.docx', 'label': 'Vinculación'},
}


@plantillas_bp.before_request
@login_required
@roles_required('Super Admin')
def before_request():
    pass


@plantillas_bp.route('/')
def lista():
    plantillas = []
    for key, info in PLANTILLAS.items():
        path = os.path.join(current_app.config['TEMPLATES_WORD_FOLDER'], info['filename'])
        plantillas.append({
            'key': key,
            'label': info['label'],
            'filename': info['filename'],
            'exists': os.path.exists(path),
            'size': os.path.getsize(path) if os.path.exists(path) else 0,
        })
    return render_template('plantillas/lista.html', plantillas=plantillas)


@plantillas_bp.route('/subir/<key>', methods=['POST'])
def subir(key):
    if key not in PLANTILLAS:
        flash('Plantilla no válida.', 'danger')
        return redirect(url_for('plantillas.lista'))

    if 'plantilla' not in request.files:
        flash('No se subió ningún archivo.', 'danger')
        return redirect(request.url)

    file = request.files['plantilla']
    if file.filename == '':
        flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(request.url)

    if not file.filename.endswith('.docx'):
        flash('El archivo debe ser un documento Word (.docx).', 'danger')
        return redirect(request.url)

    filename = PLANTILLAS[key]['filename']
    target_dir = current_app.config['TEMPLATES_WORD_FOLDER']
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, filename)
    file.save(target_path)
    flash(f'Plantilla de {PLANTILLAS[key]["label"]} actualizada.', 'success')
    return redirect(url_for('plantillas.lista'))

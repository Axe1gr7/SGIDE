import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Dependencia, Expediente
from app.decorators import roles_required, active_query

dependencias_bp = Blueprint('dependencias', __name__)

TIPOS = ['Practicas', 'Servicio', 'Ambos']
SECTORES = ['Municipal', 'Estatal', 'Salud']


@dependencias_bp.before_request
@login_required
@roles_required('Super Admin', 'Practicas', 'Servicio')
def before_request():
    pass


@dependencias_bp.route('/')
def lista():
    tipo_filter = request.args.get('tipo_filter')
    search = request.args.get('search')

    query = active_query(Dependencia)
    if tipo_filter:
        query = query.filter_by(tipo=tipo_filter)
    if search:
        query = query.filter(Dependencia.nombre.ilike(f'%{search}%'))

    dependencias = query.order_by(Dependencia.nombre).all()
    return render_template('dependencias/lista.html',
                           dependencias=dependencias,
                           tipos=TIPOS,
                           sectores=SECTORES,
                           tipo_filter=tipo_filter,
                           search=search)


@dependencias_bp.route('/crear', methods=['GET', 'POST'])
def crear():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre').strip()
            tipo = request.form.get('tipo', 'Ambos')
            sector = request.form.get('sector') or None
            domicilio = request.form.get('domicilio') or None
            contacto = request.form.get('contacto') or None
            telefono = request.form.get('telefono') or None
            correo = request.form.get('correo') or None

            if not nombre:
                flash('El nombre de la dependencia es obligatorio.', 'danger')
            else:
                dep = Dependencia(nombre=nombre, tipo=tipo, sector=sector,
                                  domicilio=domicilio, contacto=contacto,
                                  telefono=telefono, correo=correo)
                db.session.add(dep)
                db.session.commit()
                flash('Dependencia creada exitosamente.', 'success')
                return redirect(url_for('dependencias.lista'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('dependencias/form.html',
                           dependencia=None,
                           tipos=TIPOS,
                           sectores=SECTORES)


@dependencias_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
def editar(id):
    dependencia = active_query(Dependencia).filter_by(id=id).first_or_404()
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre').strip()
            if not nombre:
                flash('El nombre de la dependencia es obligatorio.', 'danger')
            else:
                dependencia.nombre = nombre
                dependencia.tipo = request.form.get('tipo', 'Ambos')
                dependencia.sector = request.form.get('sector') or None
                dependencia.domicilio = request.form.get('domicilio') or None
                dependencia.contacto = request.form.get('contacto') or None
                dependencia.telefono = request.form.get('telefono') or None
                dependencia.correo = request.form.get('correo') or None
                db.session.commit()
                flash('Dependencia actualizada.', 'success')
                return redirect(url_for('dependencias.lista'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('dependencias/form.html',
                           dependencia=dependencia,
                           tipos=TIPOS,
                           sectores=SECTORES)


@dependencias_bp.route('/<int:id>/eliminar', methods=['POST'])
def eliminar(id):
    dependencia = active_query(Dependencia).filter_by(id=id).first_or_404()
    dependencia.is_deleted = True
    db.session.commit()
    flash('Dependencia eliminada.', 'success')
    return redirect(url_for('dependencias.lista'))


@dependencias_bp.route('/importar', methods=['GET', 'POST'])
def importar():
    resultado = None
    if request.method == 'POST':
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
            resultado = procesar_excel_dependencias(filepath)
            os.remove(filepath)
            if resultado['errores']:
                flash('Importación completada con algunos errores. Revisa el resumen.', 'warning')
            else:
                flash('Importación de dependencias completada.', 'success')
        else:
            flash('Formato de archivo no válido. Usa .xlsx o .xls', 'danger')

    return render_template('dependencias/importar.html', resultado=resultado)


def procesar_excel_dependencias(filepath):
    """Procesa un Excel con columnas: nombre, tipo, sector, domicilio, contacto, telefono, correo."""
    import pandas as pd

    try:
        df = pd.read_excel(filepath, engine='openpyxl')
    except Exception as e:
        return {'insertados': 0, 'duplicados': 0, 'errores': [f'Error al leer el archivo: {str(e)}']}

    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    required = {'nombre'}
    missing = required - set(df.columns)
    if missing:
        return {'insertados': 0, 'duplicados': 0, 'errores': [f'Columnas faltantes: {", ".join(missing)}']}

    insertados = 0
    duplicados = 0
    errores = []

    for idx, row in df.iterrows():
        fila_num = idx + 2
        try:
            nombre = str(row['nombre']).strip()
            if not nombre or pd.isna(row['nombre']):
                errores.append(f'Fila {fila_num}: nombre vacío.')
                continue

            existente = Dependencia.query.filter_by(nombre=nombre, is_deleted=False).first()
            if existente:
                duplicados += 1
                continue

            tipo = str(row.get('tipo', 'Ambos')).strip() if 'tipo' in df.columns and not pd.isna(row.get('tipo', '')) else 'Ambos'
            if tipo not in TIPOS:
                tipo = 'Ambos'
            sector = str(row['sector']).strip() if 'sector' in df.columns and not pd.isna(row.get('sector', '')) else None
            domicilio = str(row['domicilio']).strip() if 'domicilio' in df.columns and not pd.isna(row.get('domicilio', '')) else None
            contacto = str(row['contacto']).strip() if 'contacto' in df.columns and not pd.isna(row.get('contacto', '')) else None
            telefono = str(row['telefono']).strip() if 'telefono' in df.columns and not pd.isna(row.get('telefono', '')) else None
            correo = str(row['correo']).strip() if 'correo' in df.columns and not pd.isna(row.get('correo', '')) else None

            dep = Dependencia(nombre=nombre, tipo=tipo, sector=sector,
                              domicilio=domicilio, contacto=contacto,
                              telefono=telefono, correo=correo)
            db.session.add(dep)
            insertados += 1
        except Exception as e:
            errores.append(f'Fila {fila_num}: {str(e)}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errores.append(f'Error al guardar: {str(e)}')

    return {'insertados': insertados, 'duplicados': duplicados, 'errores': errores}

import os
import io
import unicodedata
from datetime import date, datetime, time
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, send_file, abort)
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Alumno, Carrera, Expediente, Documento, Practica, Dependencia
from app.decorators import roles_required, active_query
from app.blueprints.dependencias import obtener_sectores_dinamicos
from app.services.logic_word import (
    FORMATO_ACREDITACION_PP_FILENAME,
    generar_documento_word,
)
from app.services.file_manager import guardar_documento, obtener_ruta_absoluta
from app.services.logic_zip import procesar_zip_pdfs
from app.services.logic_expediente import (
    cerrar_servicio_social_por_practicas,
    resolver_carrera_practicas,
    sincronizar_carreras_practicas,
    sincronizar_servicio_social_con_practicas,
)
from app.models import CarpetaCompartida, ArchivoCompartido


practicas_bp = Blueprint('practicas', __name__)
MODULO_LABEL = 'Prácticas Profesionales'
MODULO_PREFIX = 'practicas'
ESTATUS_PLANTEL = ('Activo', 'Inactivo', 'Egresado')
DOCUMENTOS_PRACTICAS_AUTO = [
    os.path.splitext(FORMATO_ACREDITACION_PP_FILENAME)[0],
]


# ── Validación del formulario de Prácticas ─────────────────────────────────

# Campos Integer del modelo con su etiqueta legible
_INTEGER_FIELDS_LABELS = {
    'no_registro':      'No. Registro',
    'consecutivo':      'Consecutivo',
    'f_inicio_dia':     'Día (F. Inicio)',
    'f_inicio_anio':    'Año (F. Inicio)',
    'f_ca_dia':         'Día (C. Aceptación)',
    'f_ca_anio':        'Año (C. Aceptación)',
    'inf_final_valor':  'Inf. Final (valor)',
    'f_ct_dia':         'Día (Constancia T.)',
    'f_ct_anio':        'Año (Constancia T.)',
}

# Campos Numeric/Decimal del modelo con su etiqueta
_NUMERIC_FIELDS_LABELS = {
    'becados':          ('Becados',        10, 2),
    'r_e_final_valor':  ('R-E-Final (valor)', 5, 2),
    'c_t_valor':        ('C.T (valor)',     5, 2),
}

# Campos Date del modelo con su etiqueta
_DATE_FIELDS_LABELS = {
    's_prac_fecha_excel': 'S. Prác. (fecha)',
    'f_inicio':           'F. Inicio',
    'c_pres_fecha_excel': 'C. Pres. (fecha)',
    'f_cp':               'F.C.P',
    'c_acep_fecha_excel': 'C. Acep. (fecha)',
    'f_ca':               'F.C.A',
    'p_trabj_fecha_excel':'P. Trabj. (fecha)',
    'f_ptr':              'F. P.Tr.',
    'i_inter_fecha_excel':'I. Inter. (fecha)',
    'f_ii':               'F.I.I.',
    'f_l_ii':             'F.L. I.I.',
    'f_i_final':          'F.I.Final',
    'f_re_final':         'F.R-E Final',
    'f_ct':               'F.C.T',
}

# Campos de año que deben validarse en un rango razonable
_YEAR_FIELDS_LABELS = {
    'f_inicio_anio': 'Año (F. Inicio)',
    'f_ca_anio':     'Año (C. Aceptación)',
    'f_ct_anio':     'Año (Constancia T.)',
}

# Límites de longitud de String basados en el modelo
_STRING_MAX_LENGTHS = {
    'no_constancia':        (50,  'No. Constancia'),
    'nombre':               (250, 'Nombre'),
    'nombre_minusculas':    (250, 'Nombre Minúsculas'),
    'matricula':            (50,  'Matrícula'),
    'telefono':             (20,  'Teléfono'),
    'correo_estudiante':    (150, 'Correo Estudiante'),
    'grado_carrera':        (30,  'Grado-Carrera'),
    'turno':                (15,  'Turno'),
    'carrera':              (50,  'Carrera'),
    'observaciones':        (20,  'Observaciones'),
    'proceso':              (30,  'Proceso'),
    'empresa':              (250, 'Empresa'),
    'sector':               (60,  'Sector'),
    'nombre_proyecto':      (300, 'Nombre del Proyecto'),
    'tel_empresa':          (20,  'Tel. Empresa'),
    'direccion_empresa':    (400, 'Dirección Empresa'),
    'correo_empresa':       (150, 'Correo Empresa'),
    'generacion':           (10,  'Generación'),
    'sexo':                 (10,  'H/M'),
    'monto':                (20,  'Monto'),
    's_prac':               (15,  'S. Prác'),
    'f_inicio_mes':         (15,  'Mes (F. Inicio)'),
    'c_pres':               (15,  'C. Pres.'),
    'c_acep':               (15,  'C. Acep'),
    'f_ca_mes':             (15,  'Mes (C. Aceptación)'),
    'p_trabj':              (15,  'P. Trabj'),
    'i_inter':              (15,  'I. Inter'),
    'estado':               (15,  'Estado'),
    'inf_final':            (15,  'Inf. Final'),
    'estado_inf_final':     (15,  'Estado (Inf. Final)'),
    'r_e_final':            (15,  'R-E-Final'),
    'cons_t':               (15,  'Cons.T'),
    'f_ct_mes':             (15,  'Mes (Constancia T.)'),
    'promedio':             (10,  'Promedio'),
    'tiempo_proceso':       (50,  'Tiempo del Proceso'),
    'carpeta':              (100, 'Carpeta'),
    'paso_por_constancia':  (100, 'Paso por Constancia'),
    'pc':                   (50,  'P.C.'),
}


def _validar_practica_form(form_data):
    """
    Valida los datos del formulario de prácticas antes de guardar.
    Retorna una lista de mensajes de error. Lista vacía = sin errores.
    Los campos vacíos se ignoran (todos los campos son opcionales).
    """
    errores = []
    anio_actual = date.today().year
    anio_min, anio_max = 1920, anio_actual + 5

    # ── Validar campos enteros ─────────────────────────────────────────
    for field, label in _INTEGER_FIELDS_LABELS.items():
        val = form_data.get(field, '').strip()
        if not val:
            continue
        try:
            int(float(val))
        except (ValueError, TypeError):
            errores.append(f'"{label}" debe ser un número entero válido.')

    # ── Validar campos de año (rango) ──────────────────────────────────
    for field, label in _YEAR_FIELDS_LABELS.items():
        val = form_data.get(field, '').strip()
        if not val:
            continue
        try:
            year = int(float(val))
            if year < anio_min or year > anio_max:
                errores.append(
                    f'"{label}" debe estar entre {anio_min} y {anio_max}.'
                )
        except (ValueError, TypeError):
            pass  # Ya capturado por la validación de enteros

    # ── Validar campos numéricos (Decimal) ─────────────────────────────
    for field, (label, precision, scale) in _NUMERIC_FIELDS_LABELS.items():
        val = form_data.get(field, '').strip()
        if not val:
            continue
        try:
            num = float(val.replace(',', '.'))
            max_digits = precision - scale
            if abs(num) >= 10 ** max_digits:
                errores.append(
                    f'"{label}" excede el máximo permitido '
                    f'({max_digits} dígitos enteros, {scale} decimales).'
                )
        except (ValueError, TypeError):
            errores.append(f'"{label}" debe ser un número válido.')

    # ── Validar campos de fecha ────────────────────────────────────────
    for field, label in _DATE_FIELDS_LABELS.items():
        val = form_data.get(field, '').strip()
        if not val:
            continue
        try:
            datetime.strptime(val, '%Y-%m-%d')
        except (ValueError, TypeError):
            errores.append(
                f'"{label}" no tiene un formato de fecha válido (AAAA-MM-DD).'
            )

    # ── Validar longitudes de cadena ───────────────────────────────────
    for field, (max_len, label) in _STRING_MAX_LENGTHS.items():
        val = form_data.get(field, '').strip()
        if not val:
            continue
        if len(val) > max_len:
            errores.append(
                f'"{label}" excede el máximo de {max_len} caracteres '
                f'({len(val)} ingresados).'
            )

    return errores


@practicas_bp.before_request
@login_required
@roles_required('Super Admin', 'Practicas')
def before_request():
    pass


# ── Menú principal ──────────────────────────────────────────────────────────

@practicas_bp.route('/')
def menu():
    return render_template('practicas/menu.html',
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)

@practicas_bp.route('/plantillas')
def plantillas():
    return redirect(url_for('plantillas.lista', modulo='p'))


# ── Submódulo: Dashboard ───────────────────────────────────────────────────

@practicas_bp.route('/dashboard')
def dashboard():
    # Mantener el mismo criterio de elegibilidad que usa el submódulo Alumnos:
    # únicamente Servicio Social finalizado.
    alumnos_candidatos = active_query(Alumno).all()
    tienen_derecho = sum(_check_ss_completo(alumno) for alumno in alumnos_candidatos)
    no_tienen_derecho = len(alumnos_candidatos) - tienen_derecho

    # Las mismas reglas de finalización se aplican en la tabla de Alumnos:
    # CONCLUIDO o constancia de terminación CONS.T = SI.
    practicas_registradas = active_query(Practica).all()
    total_practicas = len(practicas_registradas)
    estatus_counts = {estatus: 0 for estatus in Practica.OBSERVACIONES_OPTS}
    estatus_counts['SIN ESTATUS'] = 0
    for practica in practicas_registradas:
        estatus = (practica.observaciones or '').strip().upper()
        if estatus in estatus_counts and estatus != 'SIN ESTATUS':
            estatus_counts[estatus] += 1
        else:
            estatus_counts['SIN ESTATUS'] += 1
    aptos = sum(
        1 for alumno in alumnos_candidatos
        if _check_ss_completo(alumno) and not _get_practicas_for_alumno(alumno)
    ) + estatus_counts['APTO']
    concluidas = estatus_counts['CONCLUIDO']
    en_tramite = estatus_counts['EN TRÁMITE']
    sin_estatus = estatus_counts['SIN ESTATUS']
    
    # 3. Distribución por Proceso
    procesos_counts = db.session.query(
        Practica.proceso, func.count(Practica.id)
    ).filter(
        Practica.is_deleted == False
    ).group_by(
        Practica.proceso
    ).all()
    
    proceso_data = {p: 0 for p in Practica.PROCESOS}
    proceso_data['SIN PROCESO'] = 0
    for proc, count in procesos_counts:
        proceso = (proc or '').strip().upper() or 'SIN PROCESO'
        proceso_data[proceso] = proceso_data.get(proceso, 0) + count
            
    return render_template('practicas/dashboard.html',
                           tienen_derecho=tienen_derecho,
                           no_tienen_derecho=no_tienen_derecho,
                           total_practicas=total_practicas,
                           estatus_counts=estatus_counts,
                           aptos=aptos,
                           concluidas=concluidas,
                           en_tramite=en_tramite,
                           sin_estatus=sin_estatus,
                           proceso_data=proceso_data,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)


# ── Submódulo: Detalles de Prácticas ───────────────────────────────────────

# Mapeo ordenado: (campo_db, encabezado_excel)
COLUMNAS_MAPA = [
    ('no_registro',          'No. REGISTRO'),
    ('consecutivo',          'CONSECUTIVO'),
    ('no_constancia',        'No. CONSTANCIA'),
    ('nombre',               'NOMBRE'),
    ('nombre_minusculas',    'Nombre Minúsculas'),
    ('matricula',            'MATRÍCULA'),
    ('telefono',             'TELÉFONO'),
    ('correo_estudiante',    'CORREO ESTUDIANTE'),
    ('grado_carrera',        'GRADO-CARRERA'),
    ('turno',                'TURNO'),
    ('carrera',              'CARRERA'),
    ('observaciones',        'OBSERVACIONES'),
    ('proceso',              'PROCESO'),
    ('empresa',              'EMPRESA'),
    ('sector',               'SECTOR'),
    ('nombre_proyecto',      'NOMBRE DEL PROYECTO'),
    ('tel_empresa',          'TEL. EMPRESA'),
    ('direccion_empresa',    'DIRECCIÓN EMPRESA'),
    ('correo_empresa',       'CORR. EM'),
    ('generacion',           'GENERACIÓN'),
    ('sexo',                 'H/M'),
    ('becados',              'BECADOS'),
    ('monto',                'MONTO'),
    ('s_prac',               'S. PRÁC'),
    ('s_prac_fecha_excel',   'S. PRÁC.'),
    ('f_inicio',             'F. INICIO'),
    ('f_inicio_dia',         'DIA'),
    ('f_inicio_mes',         'MES'),
    ('f_inicio_anio',        'AÑO'),
    ('c_pres',               'C.PRES.'),
    ('c_pres_fecha_excel',   'C.PRES.2'),
    ('f_cp',                 'F.C.P'),
    ('c_acep',               'C. ACEP'),
    ('c_acep_fecha_excel',   'C. ACEP.'),
    ('f_ca',                 'F.C.A'),
    ('f_ca_dia',             'DIA 3'),
    ('f_ca_mes',             'MES4'),
    ('f_ca_anio',            'AÑO 5'),
    ('p_trabj',              'P. TRABJ'),
    ('p_trabj_fecha_excel',  'P. TRABJ.'),
    ('f_ptr',                'F. P.TR'),
    ('i_inter',              'I. INTER'),
    ('i_inter_fecha_excel',  'I. INTER.'),
    ('f_ii',                 'F.I.I.'),
    ('f_l_ii',               'F.L. I.I.'),
    ('estado',               'ESTADO'),
    ('inf_final',            'INF. FINAL'),
    ('inf_final_valor',      'INF. FINAL6'),
    ('f_i_final',            'F.I.FINAL'),
    ('estado_inf_final',     'ESTADO7'),
    ('r_e_final',            'R-E-FINAL'),
    ('r_e_final_valor',      'R-E-FINAL8'),
    ('f_re_final',           'F.R-E FINAL'),
    ('cons_t',               'CONS.T'),
    ('c_t_valor',            'C.T'),
    ('f_ct',                 'F.C.T'),
    ('f_ct_dia',             'DIA2'),
    ('f_ct_mes',             'MES2'),
    ('f_ct_anio',            'AÑO2'),
    ('promedio',             'PROMEDIO'),
    ('tiempo_proceso',       'TIEMPO DEL PROCESO'),
    ('resumen_observaciones','RESUMEN -OBSERVACIONES'),
    ('carpeta',              'CARPETA'),
    ('paso_por_constancia',  'PASO POR CONSTANCIA'),
    ('pc',                   'P.C.'),
]

# Filtros selector: (query_param_name, campo_db, opciones, label)
FILTROS_SELECTOR = [
    ('f_grado_carrera',   'grado_carrera',    Practica.GRADOS_CARRERA,    'Grado-Carrera'),
    ('f_turno',           'turno',            Practica.TURNOS,            'Turno'),
    ('f_carrera',         'carrera',          Practica.CARRERAS,          'Carrera'),
    ('f_observaciones',   'observaciones',    Practica.OBSERVACIONES_OPTS,'Observaciones'),
    ('f_proceso',         'proceso',          Practica.PROCESOS,          'Proceso'),
    ('f_sector',          'sector',           None,                       'Sector'),
    ('f_sexo',            'sexo',             Practica.SEXOS,             'H/M'),
    ('f_s_prac',          's_prac',           Practica.OPTS_SNC,          'S. PRÁC'),
    ('f_c_pres',          'c_pres',           Practica.OPTS_SNC,          'C.PRES.'),
    ('f_c_acep',          'c_acep',           Practica.OPTS_SNC,          'C. ACEP'),
    ('f_p_trabj',         'p_trabj',          Practica.OPTS_SNC,          'P. TRABJ'),
    ('f_i_inter',         'i_inter',          Practica.OPTS_SNC,          'I. INTER'),
    ('f_estado',          'estado',           Practica.ESTADOS,           'Estado (I.I.)'),
    ('f_inf_final',       'inf_final',        Practica.OPTS_SNC,          'INF. FINAL'),
    ('f_estado_inf',      'estado_inf_final', Practica.ESTADOS,           'Estado (Inf. Final)'),
    ('f_r_e_final',       'r_e_final',        Practica.OPTS_SNC,          'R-E-FINAL'),
    ('f_cons_t',          'cons_t',           Practica.OPTS_SNC,          'CONS.T'),
]

# Opciones del filtro CARPETA (Bloque)
CARPETA_OPTS = ['BLOQUE 1', 'BLOQUE 2', 'BLOQUE 3']

# Filtros de rango de fecha: (param_prefix, campo_db, label)
# Cada uno genera dos parámetros: {param_prefix}_desde y {param_prefix}_hasta
FILTROS_FECHA = [
    ('fd_s_prac_fecha',    's_prac_fecha_excel',   'S. PRÁC. (Fecha)'),
    ('fd_f_inicio',        'f_inicio',             'F. INICIO'),
    ('fd_c_pres_fecha',    'c_pres_fecha_excel',   'C.PRES. (Fecha)'),
    ('fd_f_cp',            'f_cp',                 'F.C.P'),
    ('fd_c_acep_fecha',    'c_acep_fecha_excel',   'C. ACEP. (Fecha)'),
    ('fd_f_ca',            'f_ca',                 'F.C.A'),
    ('fd_p_trabj_fecha',   'p_trabj_fecha_excel',  'P. TRABJ. (Fecha)'),
    ('fd_f_ptr',           'f_ptr',                'F. P.TR'),
    ('fd_i_inter_fecha',   'i_inter_fecha_excel',  'I. INTER. (Fecha)'),
    ('fd_f_ii',            'f_ii',                 'F.I.I.'),
    ('fd_f_l_ii',          'f_l_ii',               'F.L. I.I.'),
    ('fd_f_i_final',       'f_i_final',            'F.I.FINAL'),
    ('fd_f_re_final',      'f_re_final',           'F.R-E FINAL'),
    ('fd_f_ct',            'f_ct',                 'F.C.T (Paso por constancia)'),
]


def _parse_date_param(value):
    """Convierte un string de parámetro a objeto date, o None si es inválido."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _build_detalles_query():
    """Construye la query filtrada de Practica según request.args."""
    query = Practica.query.filter_by(is_deleted=False)

    practica_id = request.args.get('practica_id', type=int)
    if practica_id:
        query = query.filter(Practica.id == practica_id)

    # Búsqueda general por texto
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Practica.nombre.ilike(f'%{search}%')) |
            (Practica.matricula.ilike(f'%{search}%')) |
            (Practica.empresa.ilike(f'%{search}%')) |
            (Practica.no_constancia.ilike(f'%{search}%')) |
            (Practica.nombre_proyecto.ilike(f'%{search}%')) |
            (Practica.promedio.ilike(f'%{search}%')) |
            (Practica.resumen_observaciones.ilike(f'%{search}%')) |
            (Practica.paso_por_constancia.ilike(f'%{search}%')) |
            (Practica.pc.ilike(f'%{search}%'))
        )

    # Filtros de tipo selector
    for param_name, db_field, _options, _label in FILTROS_SELECTOR:
        val = request.args.get(param_name)
        if val:
            query = query.filter(getattr(Practica, db_field) == val)

    # Filtro por generación (texto libre)
    gen = request.args.get('f_generacion', '').strip()
    if gen:
        query = query.filter(Practica.generacion.ilike(f'%{gen}%'))

    # Filtro por CARPETA (Bloque)
    carpeta_val = request.args.get('f_carpeta', '').strip()
    if carpeta_val:
        if carpeta_val == 'BLOQUE 3':
            query = query.filter(
                (Practica.carpeta == None) | (Practica.carpeta == '')
            )
        else:
            query = query.filter(Practica.carpeta == carpeta_val)

    # Filtros de rango de fecha
    for param_prefix, db_field, _label in FILTROS_FECHA:
        desde = _parse_date_param(request.args.get(f'{param_prefix}_desde'))
        hasta = _parse_date_param(request.args.get(f'{param_prefix}_hasta'))
        col = getattr(Practica, db_field)
        if desde and hasta:
            query = query.filter(col >= desde, col <= hasta)
        elif desde:
            query = query.filter(col >= desde)
        elif hasta:
            query = query.filter(col <= hasta)

    return query.order_by(Practica.no_registro)


def _get_columnas_activas():
    """Obtiene las columnas visibles de request.args o retorna todas."""
    all_fields = [c[0] for c in COLUMNAS_MAPA]
    if 'cols' not in request.args:
        return all_fields
    cols = request.args.getlist('cols')
    # Validar contra campos existentes
    return [c for c in cols if c in all_fields]


@practicas_bp.route('/detalles')
def detalles():
    query = _build_detalles_query()
    practicas = query.all()
    columnas_activas = _get_columnas_activas()
    selected_practica_id = request.args.get('practica_id', type=int)

    # Calcular cuántos filtros están activos para el badge
    filtros_activos = 0
    if request.args.get('search', '').strip():
        filtros_activos += 1
    if request.args.get('f_generacion', '').strip():
        filtros_activos += 1
    for param_name, _db, _opts, _label in FILTROS_SELECTOR:
        if request.args.get(param_name):
            filtros_activos += 1
    if request.args.get('f_carpeta', '').strip():
        filtros_activos += 1
    for param_prefix, _db, _label in FILTROS_FECHA:
        if request.args.get(f'{param_prefix}_desde') or request.args.get(f'{param_prefix}_hasta'):
            filtros_activos += 1

    # Construir dinámicamente los filtros selectores para inyectar los sectores actuales
    filtros_selector_dinamicos = []
    sectores_dinamicos = obtener_sectores_dinamicos()
    for param_name, db_field, options, label in FILTROS_SELECTOR:
        if param_name == 'f_sector':
            filtros_selector_dinamicos.append((param_name, db_field, sectores_dinamicos, label))
        else:
            filtros_selector_dinamicos.append((param_name, db_field, options, label))

    return render_template('practicas/detalles.html',
                           practicas=practicas,
                           columnas_mapa=COLUMNAS_MAPA,
                           columnas_activas=columnas_activas,
                           filtros_selector=filtros_selector_dinamicos,
                           filtros_fecha=FILTROS_FECHA,
                           carpeta_opts=CARPETA_OPTS,
                           filtros_activos=filtros_activos,
                           selected_practica_id=selected_practica_id if len(practicas) == 1 else None,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)


@practicas_bp.route('/detalles/exportar')
def exportar_detalles():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.table import Table, TableStyleInfo

    query = _build_detalles_query()
    practicas = query.all()
    columnas_activas = _get_columnas_activas()

    # Filtrar solo las columnas visibles
    cols_export = [(f, h) for f, h in COLUMNAS_MAPA if f in columnas_activas]

    wb = Workbook()
    ws = wb.active
    ws.title = 'Prácticas Profesionales'

    if not cols_export:
        flash('Selecciona al menos una columna para exportar.', 'warning')
        return redirect(url_for('practicas.detalles', **request.args))

    # Encabezados con estilo editorial y filas de datos filtradas.
    header_font = Font(name='Aptos Display', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='12304A')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    body_border = Border(bottom=Side(style='hair', color='D9E2EC'))
    for col_idx, (field, header) in enumerate(cols_export, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = body_border

    # Escribir datos
    for row_idx, p in enumerate(practicas, start=2):
        for col_idx, (field, _header) in enumerate(cols_export, start=1):
            val = getattr(p, field, None)
            # Convertir Decimal a float
            if val is not None and hasattr(val, 'is_finite'):
                val = float(val)
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = body_border
            if hasattr(val, 'strftime'):
                cell.number_format = 'd/m/yyyy'
            cell.alignment = Alignment(vertical='top', wrap_text=False)

    # Tabla nativa de Excel: filtros desplegables, bandas y rango completo.
    last_column = ws.cell(row=1, column=len(cols_export)).column_letter
    last_row = max(2, len(practicas) + 1)
    tabla = Table(displayName='TablaPracticasExportadas', ref=f'A1:{last_column}{last_row}')
    tabla.tableStyleInfo = TableStyleInfo(
        name='TableStyleMedium2', showFirstColumn=False,
        showLastColumn=False, showRowStripes=True, showColumnStripes=False
    )
    ws.add_table(tabla)

    # Autoajustar anchos usando una muestra de valores, sin ensanchar columnas
    # por textos excepcionalmente largos.
    for col_idx, (field, header) in enumerate(cols_export, start=1):
        max_len = len(header)
        for row in range(2, min(len(practicas) + 2, 52)):
            cell_val = ws.cell(row=row, column=col_idx).value
            if cell_val:
                max_len = max(max_len, len(str(cell_val)))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 3, 38)

    ws.row_dimensions[1].height = 34
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{last_column}{last_row}'
    ws.sheet_view.showGridLines = False

    # Guardar en buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'Practicas_Profesionales_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ── Submódulo: Alumnos ─────────────────────────────────────────────────────

def _check_ss_completo(alumno):
    """
    """
    if alumno.servicio_completado:
        return True

    expediente_ss = Expediente.query.filter_by(
        alumno_id=alumno.id,
        tipo_modulo='s',
        is_deleted=False
    ).first()
    if not expediente_ss:
        return False
    total_docs = Documento.query.filter_by(
        expediente_id=expediente_ss.id,
        is_deleted=False
    ).count()
    if total_docs == 0:
        return False
    completados = Documento.query.filter(
        Documento.expediente_id == expediente_ss.id,
        Documento.is_deleted == False,
        Documento.estado.in_(['Entregado', 'Recibido'])
    ).count()
    return completados == total_docs


def _estatus_plantel_visible(alumno):
    """Evita mostrar valores documentales heredados como estatus del plantel."""
    if alumno.estatus in ESTATUS_PLANTEL:
        return alumno.estatus
    return 'Activo'


def _get_practica_for_alumno(alumno):
    """Devuelve una práctica asociada al alumno, priorizando la FK."""
    practica = Practica.query.filter_by(
        alumno_id=alumno.id, is_deleted=False
    ).order_by(Practica.id.desc()).first()
    if practica or not alumno.matricula:
        return practica
    return Practica.query.filter_by(
        matricula=alumno.matricula, is_deleted=False
    ).order_by(Practica.id.desc()).first()


def _get_practicas_for_alumno(alumno):
    """Obtiene todos los registros para calcular correctamente el estado."""
    practicas = Practica.query.filter_by(
        alumno_id=alumno.id, is_deleted=False
    ).all()
    if practicas or not alumno.matricula:
        return practicas
    return Practica.query.filter_by(
        matricula=alumno.matricula, is_deleted=False
    ).all()


def _semestre_habilitado(alumno):
    """Determina si la generación ya alcanzó el semestre de Prácticas."""
    if alumno.estatus == 'Egresado':
        return True
    if alumno.estatus != 'Activo' or alumno.anio_generacion is None:
        return False
    limite_generacion = (datetime.now().year - 2) % 100
    return alumno.anio_generacion <= limite_generacion


def _practicas_finalizadas(practicas):
    return any(
        (p.observaciones or '').strip().upper() == 'CONCLUIDO'
        or (p.cons_t or '').strip().upper() == 'SI'
        for p in practicas
    )


@practicas_bp.route('/alumnos')
def alumnos():
    sincronizar_servicio_social_con_practicas()
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    carrera_filter = request.args.get('carrera_filter')
    search = request.args.get('search', '').strip()
    estatus_filter = request.args.get('estatus_filter')
    solo_aptos = request.args.get('solo_aptos')
    tipo_consulta = request.args.get('tipo_consulta', 'todos')

    query = active_query(Alumno)

    if carrera_filter:
        query = query.filter(Alumno.carrera_id == int(carrera_filter))
    if search:
        query = query.filter(
            (Alumno.nombre.ilike(f'%{search}%')) |
            (Alumno.matricula.ilike(f'%{search}%'))
        )
    if estatus_filter in ESTATUS_PLANTEL:
        if estatus_filter == 'Activo':
            query = query.filter(Alumno.estatus == 'Activo')
        else:
            query = query.filter(Alumno.estatus == estatus_filter)
    else:
        estatus_filter = None

    all_candidatos = query.order_by(Alumno.nombre).all()
    alumnos_data = []

    for alumno in all_candidatos:
        ss_completo = _check_ss_completo(alumno)
        practicas = _get_practicas_for_alumno(alumno)
        practica = practicas[-1] if practicas else None
        practicas_concluidas = _practicas_finalizadas(practicas)

        estatus_practicas = (
            practica.observaciones
            if practica and practica.observaciones in Practica.OBSERVACIONES_OPTS
            else ('CONCLUIDO' if practicas_concluidas else ('APTO' if ss_completo else None))
        )

        # Filtro según tipo_consulta
        if tipo_consulta == 'aprobados' and not practicas_concluidas:
            continue
        elif tipo_consulta == 'aptos' and not ss_completo:
            continue
        elif tipo_consulta == 'en_tramite' and estatus_practicas != 'EN TRÁMITE':
            continue

        if solo_aptos and not ss_completo:
            continue

        alumnos_data.append({
            'alumno': alumno,
            'estatus_plantel': _estatus_plantel_visible(alumno),
            'ss_completo': ss_completo,
            'apto_practicas': ss_completo,
            'estatus_practicas': estatus_practicas,
            'tiene_practica': practica is not None,
            'practica': practica,
            'practica_id': practica.id if practica else None,
            'practicas_finalizadas': practicas_concluidas,
        })

    # Paginación manual para mantener filtros precisos
    total = len(alumnos_data)
    per_page = 20
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    paginated_alumnos = alumnos_data[start:end]

    class FakePagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page if total > 0 else 1
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1
            self.items = items

        def iter_pages(self, left_edge=2, left_current=2,
                       right_current=5, right_edge=2):
            """Expone la misma interfaz de paginación que Flask-SQLAlchemy."""
            last_num = 0
            for num in range(1, self.pages + 1):
                if (
                    num <= left_edge
                    or (num > self.page - left_current - 1
                        and num < self.page + right_current)
                    or num > self.pages - right_edge
                ):
                    if last_num + 1 != num:
                        yield None
                    yield num
                    last_num = num

    pagination = FakePagination(page, per_page, total, paginated_alumnos)

    carreras = active_query(Carrera).all()
    estatuses = ESTATUS_PLANTEL

    return render_template('practicas/alumnos.html',
                           alumnos_data=paginated_alumnos,
                           pagination=pagination,
                           carreras=carreras,
                           estatuses=estatuses,
                           carrera_filter=carrera_filter,
                           search=search,
                           estatus_filter=estatus_filter,
                           solo_aptos=solo_aptos,
                           tipo_consulta=tipo_consulta,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)


# ── Expediente de Prácticas Profesionales ──────────────────────────────────

def _expediente_practicas_de_alumno(alumno_id):
    return active_query(Expediente).filter_by(
        alumno_id=alumno_id, tipo_modulo='p'
    ).first_or_404()


def _dependencia_de_practica(practica):
    if not practica or not practica.empresa:
        return None
    return active_query(Dependencia).filter(
        db.func.lower(Dependencia.nombre) == practica.empresa.strip().lower()
    ).first()


def _asignar_dependencia_y_documentos_practicas(alumno, nombre_dependencia, dependencia=None):
    """Asocia la dependencia, si existe, e inicializa el formato único de PP."""
    expediente = active_query(Expediente).filter_by(
        alumno_id=alumno.id, tipo_modulo='p'
    ).first()
    if not expediente:
        return None

    if dependencia is None and nombre_dependencia:
        dependencia = active_query(Dependencia).filter(
            db.func.lower(Dependencia.nombre) == nombre_dependencia.strip().lower()
        ).first()

    if dependencia:
        expediente.dependencia_id = dependencia.id
    for nombre_formato in DOCUMENTOS_PRACTICAS_AUTO:
        existe = active_query(Documento).filter_by(
            expediente_id=expediente.id,
            nombre_formato=nombre_formato,
        ).first()
        if not existe:
            db.session.add(Documento(
                expediente_id=expediente.id,
                nombre_formato=nombre_formato,
                estado='Pendiente',
            ))
    return dependencia


def _normalizar_dato_dependencia(valor):
    """Normaliza un dato para comparar dependencias sin diferencias de formato."""
    texto = '' if valor is None else str(valor).strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return ' '.join(texto.casefold().split())


def _buscar_dependencia_exacta(nombre, sector, telefono, domicilio, correo):
    """Busca una dependencia activa comparando todos sus datos editables."""
    if not _normalizar_dato_dependencia(nombre):
        return None

    candidatas = active_query(Dependencia).filter(
        Dependencia.tipo.in_(['Practicas', 'Ambos'])
    ).all()
    valores = (nombre, sector, telefono, domicilio, correo)
    for dependencia in candidatas:
        actuales = (
            dependencia.nombre,
            dependencia.sector,
            dependencia.telefono,
            dependencia.domicilio,
            dependencia.correo,
        )
        if all(
            _normalizar_dato_dependencia(actual) == _normalizar_dato_dependencia(nuevo)
            for actual, nuevo in zip(actuales, valores)
        ):
            return dependencia
    return None


def _resolver_dependencia_practicas(formulario):
    """Obtiene la dependencia seleccionada o crea una nueva sin duplicarla."""
    dependencia_id = formulario.get('dependencia_id', type=int)
    crear = formulario.get('crear_dependencia') == '1'

    if dependencia_id and not crear:
        dependencia = active_query(Dependencia).filter(
            Dependencia.id == dependencia_id,
            Dependencia.tipo.in_(['Practicas', 'Ambos']),
        ).first()
        if not dependencia:
            raise ValueError('La dependencia seleccionada no está disponible.')
        return dependencia

    nombre = (formulario.get('empresa_nueva') or formulario.get('empresa') or '').strip()
    if not nombre or nombre == 'Otra':
        raise ValueError('Selecciona una dependencia o activa el botón + para registrarla.')

    sector = (formulario.get('sector') or '').strip() or None
    telefono = (formulario.get('tel_empresa') or '').strip() or None
    domicilio = (formulario.get('direccion_empresa') or '').strip() or None
    correo = (formulario.get('correo_empresa') or '').strip() or None
    dependencia = _buscar_dependencia_exacta(
        nombre, sector, telefono, domicilio, correo
    )
    if dependencia:
        return dependencia

    dependencia = Dependencia(
        nombre=nombre,
        tipo='Practicas',
        sector=sector,
        telefono=telefono,
        domicilio=domicilio,
        correo=correo,
    )
    db.session.add(dependencia)
    db.session.flush()
    return dependencia


def _siguiente_numero_practica(campo, excluir_id=None):
    query = active_query(Practica)
    if excluir_id:
        query = query.filter(Practica.id != excluir_id)
    ultimo = query.with_entities(db.func.max(getattr(Practica, campo))).scalar()
    return (ultimo or 0) + 1


def _sincronizar_datos_practica(practica, alumno, dependencia=None):
    practica.nombre = alumno.nombre
    practica.nombre_minusculas = (alumno.nombre or '').title() or None
    practica.matricula = alumno.matricula
    practica.carrera = alumno.carrera.nombre.upper() if alumno.carrera else None
    practica.generacion = alumno.generacion_completa if alumno.generacion_completa != 'Pendiente' else None

    dependencia = _asignar_dependencia_y_documentos_practicas(
        alumno, practica.empresa, dependencia=dependencia
    )
    if dependencia:
        practica.empresa = dependencia.nombre
        practica.sector = dependencia.sector
        practica.tel_empresa = dependencia.telefono
        practica.direccion_empresa = dependencia.domicilio
        practica.correo_empresa = dependencia.correo
    return dependencia


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente')
def expediente(alumno_id):
    alumno = active_query(Alumno).filter_by(id=alumno_id).first_or_404()
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    practica = _get_practica_for_alumno(alumno)
    documentos = active_query(Documento).filter_by(
        expediente_id=expediente_obj.id
    ).all()
    return render_template(
        'expedientes/detalle.html',
        expediente=expediente_obj,
        alumno=alumno,
        practica=practica,
        dependencia_practicas=_dependencia_de_practica(practica),
        documentos=documentos,
        dependencias=[],
        sectores=[],
        es_practicas=True,
        es_servicio=False,
        modulo_label=MODULO_LABEL,
        modulo_tipo='p',
        modulo_prefix='practicas',
    )


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente/documento/crear', methods=['GET', 'POST'])
def crear_documento_expediente(alumno_id):
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    if request.method == 'POST':
        archivo = request.files.get('archivo')
        ruta_archivo = None
        estado = request.form.get('estado') or 'Pendiente'
        if archivo and archivo.filename:
            ruta_archivo = guardar_documento(expediente_obj, archivo)
            estado = 'Entregado'
        documento = Documento(
            expediente_id=expediente_obj.id,
            nombre_formato=request.form.get('nombre_formato', '').strip(),
            estado=estado,
            observaciones=request.form.get('observaciones'),
            ruta_archivo=ruta_archivo,
        )
        db.session.add(documento)
        db.session.commit()
        flash('Documento de Prácticas agregado.', 'success')
        return redirect(url_for('practicas.expediente', alumno_id=alumno_id))

    return render_template(
        'expedientes/documento_form.html',
        expediente=expediente_obj,
        documento=None,
        modulo_label=MODULO_LABEL,
        modulo_prefix='practicas',
        es_practicas=True,
        form_action=url_for('practicas.crear_documento_expediente', alumno_id=alumno_id),
    )


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente/documento/<int:doc_id>/editar', methods=['GET', 'POST'])
def editar_documento_expediente(alumno_id, doc_id):
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    documento = active_query(Documento).filter_by(
        id=doc_id, expediente_id=expediente_obj.id
    ).first_or_404()
    if request.method == 'POST':
        documento.nombre_formato = request.form.get('nombre_formato', '').strip()
        documento.estado = request.form.get('estado') or 'Pendiente'
        documento.observaciones = request.form.get('observaciones')
        archivo = request.files.get('archivo')
        if archivo and archivo.filename:
            documento.ruta_archivo = guardar_documento(expediente_obj, archivo)
            documento.estado = 'Entregado'
        db.session.commit()
        flash('Documento de Prácticas actualizado.', 'success')
        return redirect(url_for('practicas.expediente', alumno_id=alumno_id))

    return render_template(
        'expedientes/documento_form.html',
        expediente=expediente_obj,
        documento=documento,
        modulo_label=MODULO_LABEL,
        modulo_prefix='practicas',
        es_practicas=True,
        form_action=url_for(
            'practicas.editar_documento_expediente',
            alumno_id=alumno_id,
            doc_id=doc_id,
        ),
    )


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente/documento/<int:doc_id>/eliminar', methods=['POST'])
def eliminar_documento_expediente(alumno_id, doc_id):
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    documento = active_query(Documento).filter_by(
        id=doc_id, expediente_id=expediente_obj.id
    ).first_or_404()
    documento.is_deleted = True
    db.session.commit()
    flash('Documento de Prácticas eliminado.', 'success')
    return redirect(url_for('practicas.expediente', alumno_id=alumno_id))


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente/documento/<int:doc_id>/descargar')
def descargar_archivo_expediente(alumno_id, doc_id):
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    documento = active_query(Documento).filter_by(
        id=doc_id, expediente_id=expediente_obj.id
    ).first_or_404()
    ruta_absoluta = obtener_ruta_absoluta(documento.ruta_archivo)
    if not ruta_absoluta or not os.path.exists(ruta_absoluta):
        abort(404)
    return send_file(
        ruta_absoluta,
        as_attachment=True,
        download_name=os.path.basename(documento.ruta_archivo),
    )


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente/generar-word', methods=['POST'])
def generar_word_expediente(alumno_id):
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    try:
        output_path, filename = generar_documento_word(
            expediente_obj.alumno_id, 'p',
            template_name=FORMATO_ACREDITACION_PP_FILENAME,
        )
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el formato: {str(e)}', 'danger')
        return redirect(url_for('practicas.expediente', alumno_id=alumno_id))


@practicas_bp.route('/alumnos/<int:alumno_id>/expediente/documento/<int:doc_id>/generar-word', methods=['POST'])
def generar_word_documento_expediente(alumno_id, doc_id):
    expediente_obj = _expediente_practicas_de_alumno(alumno_id)
    documento = active_query(Documento).filter_by(
        id=doc_id, expediente_id=expediente_obj.id
    ).first_or_404()
    try:
        output_path, filename = generar_documento_word(
            expediente_obj.alumno_id, 'p',
            template_name=FORMATO_ACREDITACION_PP_FILENAME,
        )
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error al generar el formato {documento.nombre_formato}: {str(e)}', 'danger')
        return redirect(url_for('practicas.expediente', alumno_id=alumno_id))


# ── Asignar Prácticas (formulario) ─────────────────────────────────────────

@practicas_bp.route('/alumnos/<int:alumno_id>/asignar', methods=['GET', 'POST'])
def asignar(alumno_id):
    alumno = active_query(Alumno).filter_by(id=alumno_id).first_or_404()

    if request.method == 'POST':
        # ── Validar formulario antes de procesar ───────────────────────
        errores = _validar_practica_form(request.form)
        if errores:
            for error in errores:
                flash(error, 'danger')
            return redirect(request.url)

        practica = Practica()
        # Mantener la relación con el alumno y su expediente p; la matrícula
        # visible puede cambiar, pero la FK conserva la integración.
        practica.alumno_id = alumno.id

        # Helper to get optional form values
        def fv(name):
            val = request.form.get(name)
            return val if val and val.strip() else None

        def fv_int(name):
            val = fv(name)
            if val:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None
            return None

        def fv_float(name):
            val = fv(name)
            if val:
                try:
                    return float(val.replace(',', '.'))
                except (ValueError, TypeError):
                    return None
            return None

        def fv_date(name):
            val = fv(name)
            if val:
                try:
                    return datetime.strptime(val, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    return None
            return None

        # ── Col 1-8: Datos personales ──────────────────────────────────
        practica.no_registro = fv_int('no_registro')
        practica.no_registro = practica.no_registro or _siguiente_numero_practica('no_registro')
        practica.consecutivo = _siguiente_numero_practica('consecutivo')
        practica.no_constancia = fv('no_constancia')
        practica.nombre = fv('nombre')
        practica.nombre_minusculas = fv('nombre_minusculas')
        practica.matricula = fv('matricula')
        practica.telefono = fv('telefono')
        practica.correo_estudiante = fv('correo_estudiante')

        # ── Col 9-13: Académicos ───────────────────────────────────────
        practica.grado_carrera = fv('grado_carrera')
        practica.turno = fv('turno')
        practica.carrera = fv('carrera')
        practica.observaciones = fv('observaciones')
        practica.proceso = fv('proceso')

        # ── Col 14-19: Empresa ─────────────────────────────────────────
        try:
            dependencia = _resolver_dependencia_practicas(request.form)
        except ValueError as error:
            flash(str(error), 'danger')
            return redirect(request.url)
        practica.empresa = dependencia.nombre
        practica.sector = fv('sector')
        practica.nombre_proyecto = fv('nombre_proyecto')
        practica.tel_empresa = fv('tel_empresa')
        practica.direccion_empresa = fv('direccion_empresa')
        practica.correo_empresa = fv('correo_empresa')

        # ── Col 20-23: Personales ──────────────────────────────────────
        practica.generacion = fv('generacion')
        practica.sexo = fv('sexo')
        practica.becados = fv_float('becados')
        practica.monto = fv('monto')

        # ── Col 24-29: Solicitud de Prácticas ──────────────────────────
        practica.s_prac = fv('s_prac')
        practica.s_prac_fecha_excel = fv_date('s_prac_fecha_excel')
        practica.f_inicio = fv_date('f_inicio')
        practica.f_inicio_dia = fv_int('f_inicio_dia')
        practica.f_inicio_mes = fv('f_inicio_mes')
        practica.f_inicio_anio = fv_int('f_inicio_anio')

        # ── Col 30-32: Carta de Presentación ───────────────────────────
        practica.c_pres = fv('c_pres')
        practica.c_pres_fecha_excel = fv_date('c_pres_fecha_excel')
        practica.f_cp = fv_date('f_cp')

        # ── Col 33-38: Carta de Aceptación ─────────────────────────────
        practica.c_acep = fv('c_acep')
        practica.c_acep_fecha_excel = fv_date('c_acep_fecha_excel')
        practica.f_ca = fv_date('f_ca')
        practica.f_ca_dia = fv_int('f_ca_dia')
        practica.f_ca_mes = fv('f_ca_mes')
        practica.f_ca_anio = fv_int('f_ca_anio')

        # ── Col 39-41: Plan de Trabajo ─────────────────────────────────
        practica.p_trabj = fv('p_trabj')
        practica.p_trabj_fecha_excel = fv_date('p_trabj_fecha_excel')
        practica.f_ptr = fv_date('f_ptr')

        # ── Col 42-46: Informe Intermedio ──────────────────────────────
        practica.i_inter = fv('i_inter')
        practica.i_inter_fecha_excel = fv_date('i_inter_fecha_excel')
        practica.f_ii = fv_date('f_ii')
        practica.f_l_ii = fv_date('f_l_ii')
        practica.estado = fv('estado')

        # ── Col 47-50: Informe Final ───────────────────────────────────
        practica.inf_final = fv('inf_final')
        practica.inf_final_valor = fv_int('inf_final_valor')
        practica.f_i_final = fv_date('f_i_final')
        practica.estado_inf_final = fv('estado_inf_final')

        # ── Col 51-53: Revisión-Entrega Final ──────────────────────────
        practica.r_e_final = fv('r_e_final')
        practica.r_e_final_valor = fv_float('r_e_final_valor')
        practica.f_re_final = fv_date('f_re_final')

        # ── Col 54-59: Constancia de Terminación ───────────────────────
        practica.cons_t = fv('cons_t')
        practica.c_t_valor = fv_float('c_t_valor')
        practica.f_ct = fv_date('f_ct')
        practica.f_ct_dia = fv_int('f_ct_dia')
        practica.f_ct_mes = fv('f_ct_mes')
        practica.f_ct_anio = fv_int('f_ct_anio')

        # ── Col 60-65: Cierre ──────────────────────────────────────────
        practica.promedio = fv('promedio')
        practica.tiempo_proceso = fv('tiempo_proceso')
        practica.resumen_observaciones = fv('resumen_observaciones')
        practica.carpeta = fv('carpeta')
        practica.paso_por_constancia = fv('paso_por_constancia')
        practica.pc = fv('pc')

        _sincronizar_datos_practica(practica, alumno, dependencia=dependencia)
        db.session.add(practica)
        db.session.flush()
        cerrar_servicio_social_por_practicas(alumno)
        db.session.commit()
        flash('Registro de prácticas creado exitosamente.', 'success')
        return redirect(url_for('practicas.alumnos'))

    # GET: pre-fill from alumno data
    prefill = {
        'no_registro': _siguiente_numero_practica('no_registro'),
        'consecutivo': _siguiente_numero_practica('consecutivo'),
        'nombre': alumno.nombre or '',
        'nombre_minusculas': (alumno.nombre or '').title(),
        'matricula': alumno.matricula or '',
        'carrera': alumno.carrera.nombre.upper() if alumno.carrera else '',
        'generacion': alumno.generacion_completa if alumno.generacion_completa != 'Pendiente' else '',
    }

    # Fetch dependencias that are suitable for Prácticas
    dependencias = Dependencia.query.filter(
        Dependencia.tipo.in_(['Practicas', 'Ambos']),
        Dependencia.is_deleted == False
    ).order_by(Dependencia.nombre).all()

    return render_template('practicas/asignar_form.html',
                           alumno=alumno,
                           prefill=prefill,
                           practica_model=Practica,
                           dependencias=dependencias,
                           sectores=obtener_sectores_dinamicos(),
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)


# ── Exportar a Compartidos ─────────────────────────────────────────────────

@practicas_bp.route('/exportar-compartidos', methods=['POST'])
def exportar_compartidos():
    import pandas as pd

    carpeta_id = request.form.get('carpeta_id')
    nueva_carpeta = request.form.get('nueva_carpeta')
    nombre_archivo = request.form.get('nombre_archivo', 'Reporte_Practicas')

    if nueva_carpeta:
        carpeta = CarpetaCompartida(nombre=nueva_carpeta, created_by_id=current_user.id)
        db.session.add(carpeta)
        db.session.commit()
        carpeta_id = carpeta.id
    elif carpeta_id:
        carpeta = active_query(CarpetaCompartida).filter_by(id=carpeta_id).first_or_404()
    else:
        flash('Debe seleccionar o crear una carpeta.', 'danger')
        return redirect(url_for(f'{MODULO_PREFIX}.detalles'))

    # Reutilizar la misma query que detalles para respetar filtros
    query = _build_detalles_query()
    practicas = query.all()

    data = []
    for p in practicas:
        data.append({
            'No. Registro': p.no_registro,
            'No. Constancia': p.no_constancia,
            'Nombre': p.nombre,
            'Matrícula': p.matricula,
            'Carrera': p.carrera,
            'Turno': p.turno,
            'Observaciones': p.observaciones,
            'Proceso': p.proceso,
            'Empresa': p.empresa,
            'Sector': p.sector,
            'Generación': p.generacion,
            'Sexo': p.sexo,
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
    return redirect(url_for(f'{MODULO_PREFIX}.detalles'))



# ── Ver Detalles de Práctica ───────────────────────────────────────────────

@practicas_bp.route('/alumnos/<int:alumno_id>/detalle')
def detalle_practica(alumno_id):
    alumno = active_query(Alumno).filter_by(id=alumno_id).first_or_404()
    practica = Practica.query.filter_by(
        alumno_id=alumno.id,
        is_deleted=False
    ).order_by(Practica.id.desc()).first()
    if not practica and alumno.matricula:
        practica = Practica.query.filter_by(
            matricula=alumno.matricula,
            is_deleted=False
        ).order_by(Practica.id.desc()).first()
    if not practica:
        from flask import abort
        abort(404)

    return render_template('practicas/detalle_practica.html',
                           alumno=alumno,
                           practica=practica,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)


@practicas_bp.route('/detalles/<int:practica_id>/editar', methods=['GET', 'POST'])
def editar_practica(practica_id):
    practica = active_query(Practica).filter_by(id=practica_id).first_or_404()
    alumno = practica.alumno or active_query(Alumno).filter_by(
        matricula=practica.matricula
    ).first()
    if not alumno:
        abort(404)

    if request.method == 'POST':
        # ── Validar formulario antes de procesar ───────────────────────
        errores = _validar_practica_form(request.form)
        if errores:
            for error in errores:
                flash(error, 'danger')
            return redirect(request.url)

        consecutivo_original = practica.consecutivo
        date_fields = {
            field for field, column in Practica.__table__.columns.items()
            if str(column.type).upper().startswith('DATE')
        }
        numeric_fields = {'becados', 'r_e_final_valor', 'c_t_valor'}
        integer_fields = {
            'no_registro', 'consecutivo', 'f_inicio_dia', 'f_inicio_anio',
            'f_ca_dia', 'f_ca_anio', 'inf_final_valor', 'f_ct_dia', 'f_ct_anio'
        }
        for field in COLUMNAS_MAPA:
            nombre_campo = field[0]
            valor = request.form.get(nombre_campo, '').strip()
            if nombre_campo in date_fields:
                valor = datetime.strptime(valor, '%Y-%m-%d').date() if valor else None
            elif nombre_campo in numeric_fields:
                try:
                    valor = float(valor.replace(',', '.')) if valor else None
                except ValueError:
                    valor = None
            elif nombre_campo in integer_fields:
                try:
                    valor = int(float(valor)) if valor else None
                except ValueError:
                    valor = None
            else:
                valor = valor or None
            if nombre_campo == 'observaciones' and valor not in (None, 'APTO', 'EN TRÁMITE', 'CONCLUIDO', 'BAJA'):
                valor = None
            setattr(practica, nombre_campo, valor)

        practica.consecutivo = consecutivo_original or _siguiente_numero_practica(
            'consecutivo', excluir_id=practica.id
        )
        _sincronizar_datos_practica(practica, alumno)
        db.session.commit()
        flash('Registro de prácticas actualizado exitosamente.', 'success')
        return redirect(url_for('practicas.detalles', practica_id=practica.id))

    dependencias = Dependencia.query.filter(
        Dependencia.tipo.in_(['Practicas', 'Ambos']),
        Dependencia.is_deleted == False
    ).order_by(Dependencia.nombre).all()
    return render_template(
        'practicas/asignar_form.html', alumno=alumno, practica=practica,
        prefill={}, practica_model=Practica, dependencias=dependencias,
        sectores=obtener_sectores_dinamicos(),
        modulo_label=MODULO_LABEL, modulo_prefix=MODULO_PREFIX,
        form_action=url_for('practicas.editar_practica', practica_id=practica.id),
        form_title='Editar Registro de Prácticas', form_submit='Actualizar Registro',
        practica_data={
            field: (
                value.isoformat() if hasattr(value, 'isoformat')
                else value if value is None or isinstance(value, (str, int, float, bool))
                else str(value)
            )
            for field, value in (
                (field, getattr(practica, field)) for field, _header in COLUMNAS_MAPA
            )
        }
    )


@practicas_bp.route('/detalles/<int:practica_id>/eliminar', methods=['POST'])
def eliminar_practica(practica_id):
    practica = active_query(Practica).filter_by(id=practica_id).first_or_404()
    practica.is_deleted = True
    db.session.commit()
    flash('Registro de prácticas eliminado.', 'success')
    return redirect(url_for('practicas.detalles'))


# ── Submódulo: Importación Masiva ──────────────────────────────────────────

@practicas_bp.route('/importar', methods=['GET', 'POST'])
def importar():
    resultado = None
    tipo_importacion = request.args.get('tipo_importacion', 'menu')
    if request.method == 'POST':
        tipo_importacion = request.form.get('tipo_importacion', 'registros_practicas')
        if 'archivo_excel' not in request.files:
            flash('No se subió ningún archivo.', 'danger')
            return redirect(request.url)

        file = request.files['archivo_excel']
        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'danger')
            return redirect(request.url)

        if file and file.filename.lower().endswith(('.xlsx', '.xls')):
            # Ensure the /tmp or similar directory exists, or just use a local tmp folder
            import tempfile
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, secure_filename(file.filename))
            file.save(filepath)

            try:
                if tipo_importacion == 'dependencias':
                    from app.blueprints.dependencias import procesar_excel_dependencias
                    resultado = procesar_excel_dependencias(filepath)
                else:
                    tipo_importacion = 'registros_practicas'
                    resultado = procesar_excel_practicas(filepath)
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            if resultado['errores']:
                flash('Importación completada con algunos errores. Revisa el resumen.', 'warning')
            else:
                mensaje = ('Importación de dependencias completada exitosamente.'
                           if tipo_importacion == 'dependencias'
                           else 'Importación de prácticas completada exitosamente.')
                flash(mensaje, 'success')
        else:
            flash('Formato de archivo no válido. Usa .xlsx o .xls', 'danger')

    return render_template('practicas/importar.html',
                           resultado=resultado,
                           columnas_mapa=COLUMNAS_MAPA,
                           tipo_importacion=tipo_importacion,
                           modulo_label=MODULO_LABEL,
                           modulo_prefix=MODULO_PREFIX)


def procesar_excel_practicas(filepath):
    import pandas as pd
    from app.services.logic_expediente import crear_expedientes_alumno, registrar_alumno

    # Repara alumnos históricos antes de incorporar nuevas prácticas.
    sincronizar_servicio_social_con_practicas()
    sincronizar_carreras_practicas()

    def normalizar(valor):
        texto = '' if valor is None else str(valor).strip()
        if texto.lower() in ('nan', 'nat', 'none'):
            return ''
        texto = unicodedata.normalize('NFD', texto)
        return ''.join(c for c in texto if unicodedata.category(c) != 'Mn').upper()

    def matricula_limpia(valor):
        texto = normalizar(valor)
        return texto[:-2] if texto.endswith('.0') else texto

    def fecha_limpia(valor):
        """Convierte valores de Excel a date y evita enviar time a PostgreSQL."""
        if valor is None or pd.isna(valor):
            return None
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date) and not isinstance(valor, datetime):
            return valor
        if isinstance(valor, time):
            return None
        if isinstance(valor, (int, float)):
            try:
                return (pd.Timestamp('1899-12-30') + pd.to_timedelta(valor, unit='D')).date()
            except (ValueError, TypeError, OverflowError):
                return None
        try:
            convertido = pd.to_datetime(str(valor).strip(), errors='coerce')
            return None if pd.isna(convertido) else convertido.date()
        except (ValueError, TypeError):
            return None

    try:
        # Se importa únicamente la hoja activa del libro; las demás hojas se ignoran.
        from openpyxl import load_workbook
        workbook = load_workbook(filepath, read_only=True, data_only=True)
        active_sheet = workbook.active.title
        workbook.close()
        raw = pd.read_excel(filepath, sheet_name=active_sheet, engine='openpyxl', header=None)
    except Exception as e:
        return {'insertados': 0, 'duplicados': 0, 'errores': [f'Error al leer el archivo: {str(e)}']}

    # Se comparan encabezados sin acentos ni puntuación para aceptar variantes
    # como MATRICULA/MATRÍCULA y DIRECCION/DIRECCIÓN.
    def clave_encabezado(valor):
        return ''.join(c for c in normalizar(valor) if c.isalnum())

    campos_por_encabezado = {}
    for field, header in COLUMNAS_MAPA:
        campos_por_encabezado.setdefault(clave_encabezado(header), []).append(field)
    header_row_idx = -1
    mejor_mapa = {}
    max_matches = 0
    for row_idx in range(min(20, len(raw))):
        mapa = {}
        ocurrencias = {}
        for col_idx, header in enumerate(raw.iloc[row_idx].tolist()):
            clave = clave_encabezado(header)
            candidatos = campos_por_encabezado.get(clave, [])
            ocurrencia = ocurrencias.get(clave, 0)
            if ocurrencia < len(candidatos):
                mapa[col_idx] = candidatos[ocurrencia]
                ocurrencias[clave] = ocurrencia + 1
        if len(mapa) > max_matches:
            header_row_idx, mejor_mapa, max_matches = row_idx, mapa, len(mapa)

    if header_row_idx < 0:
        return {'insertados': 0, 'duplicados': 0, 'errores': ['No se encontró ninguna fila con encabezados reconocibles.']}

    df = raw.iloc[header_row_idx + 1:].reset_index(drop=True)
    insertados = duplicados = 0
    errores = []
    registros_vistos = set()
    date_fields = {
        field for field, column in Practica.__table__.columns.items()
        if str(column.type).upper().startswith('DATE')
    }
    numeric_fields = {'becados', 'r_e_final_valor', 'c_t_valor'}
    integer_fields = {
        'no_registro', 'consecutivo', 'f_inicio_dia', 'f_inicio_anio',
        'f_ca_dia', 'f_ca_anio', 'inf_final_valor', 'f_ct_dia', 'f_ct_anio'
    }

    def buscar_carrera(valor):
        return resolver_carrera_practicas(valor)

    def buscar_alumno(matricula, nombre):
        if matricula:
            # Una matrícula nueva no debe enlazarse por coincidencia de nombre.
            return Alumno.query.filter_by(
                matricula=matricula, is_deleted=False
            ).first()
        if nombre:
            alumnos = Alumno.query.filter(Alumno.is_deleted == False).all()
            nombre_clave = normalizar(nombre)
            return next((a for a in alumnos if normalizar(a.nombre) == nombre_clave), None)
        return None

    def buscar_o_crear_dependencia(nombre, valores):
        nombre = nombre.strip()
        dependencia = Dependencia.query.filter(
            db.func.lower(Dependencia.nombre) == nombre.lower(),
            Dependencia.is_deleted == False,
        ).first()
        if dependencia:
            return dependencia

        def texto_campo(campo):
            valor = valores.get(campo)
            if valor is None or pd.isna(valor):
                return None
            texto = str(valor).strip()
            return texto or None

        dependencia = Dependencia(
            nombre=nombre,
            tipo='Practicas',
            sector=texto_campo('sector'),
            domicilio=texto_campo('direccion_empresa'),
            telefono=texto_campo('tel_empresa'),
            correo=texto_campo('correo_empresa'),
        )
        db.session.add(dependencia)
        db.session.flush()
        return dependencia

    def estatus_practica(valor):
        estado = normalizar(valor)
        if estado == 'EN TRAMITE':
            return 'EN TRÁMITE'
        if estado == 'CONCLUIDO':
            return 'CONCLUIDO'
        if estado == 'BAJA':
            return 'BAJA'
        return None

    for idx, row in df.iterrows():
        fila_num = header_row_idx + idx + 2
        savepoint = db.session.begin_nested()
        try:
            valores = {}
            for col_idx, field in mejor_mapa.items():
                valor = row.iloc[col_idx] if col_idx < len(row) else None
                if not pd.isna(valor):
                    valores[field] = valor

            no_registro = valores.get('no_registro')
            try:
                registro_numerado = (
                    no_registro is not None
                    and not pd.isna(no_registro)
                    and str(no_registro).strip() != ''
                    and float(no_registro).is_integer()
                )
            except (TypeError, ValueError):
                registro_numerado = False
            if not registro_numerado:
                savepoint.rollback()
                continue

            no_registro = int(float(no_registro))
            if no_registro in registros_vistos or Practica.query.filter_by(
                no_registro=no_registro, is_deleted=False
            ).first() is not None:
                savepoint.rollback()
                duplicados += 1
                continue
            registros_vistos.add(no_registro)

            matricula = matricula_limpia(valores.get('matricula'))
            nombre = str(valores.get('nombre', '')).strip()
            no_constancia = str(valores.get('no_constancia', '')).strip()
            # El alumno es una entidad compartida; su existencia nunca debe
            # impedir la inserción de la fila independiente de Practica.
            alumno = buscar_alumno(matricula, nombre)
            alumno_existente = alumno is not None
            carrera = buscar_carrera(valores.get('carrera'))
            generacion = str(valores.get('generacion', '')).strip()
            anio_generacion = None
            if generacion and generacion.split('-')[0].isdigit():
                anio_generacion = int(generacion.split('-')[0])

            if not alumno:
                alumno, _ = registrar_alumno(
                    nombre=nombre or None,
                    matricula=matricula or None,
                    anio_generacion=anio_generacion,
                    carrera_id=carrera.id if carrera else None,
                    carrera_prefijo=carrera.prefijo_id if carrera else None,
                    estatus='Activo',
                )
            else:
                if nombre and not alumno.nombre:
                    alumno.nombre = nombre
                if carrera:
                    alumno.carrera_id = carrera.id
                if anio_generacion and not alumno.anio_generacion:
                    alumno.anio_generacion = anio_generacion
                tipos_existentes = {
                    expediente.tipo_modulo
                    for expediente in alumno.expedientes.filter_by(is_deleted=False).all()
                }
                tipos_faltantes = {'p', 's', 'v'} - tipos_existentes
                if tipos_faltantes:
                    expedientes_nuevos = crear_expedientes_alumno(alumno)
                    for expediente in expedientes_nuevos:
                        if expediente.tipo_modulo not in tipos_faltantes:
                            db.session.delete(expediente)

            empresa = valores.get('empresa')
            if empresa is not None and not pd.isna(empresa):
                empresa = str(empresa).strip()
            if empresa:
                buscar_o_crear_dependencia(empresa, valores)

            practica = Practica()

            practica.alumno_id = alumno.id if alumno else None
            practica.matricula = matricula or None
            for field, value in valores.items():
                if field in ('matricula', 'nombre'):
                    value = matricula if field == 'matricula' else str(value).strip()
                elif field == 'observaciones':
                    value = estatus_practica(value)
                    if value is None:
                        continue
                if field in date_fields:
                    fecha = fecha_limpia(value)
                    if fecha is not None:
                        setattr(practica, field, fecha)
                elif field in numeric_fields:
                    if isinstance(value, (datetime, date, time)):
                        continue
                    try:
                        numero = float(value)
                        # r_e_final_valor y c_t_valor son NUMERIC(5,2).
                        if field in {'r_e_final_valor', 'c_t_valor'} and abs(numero) >= 1000:
                            continue
                        setattr(practica, field, numero)
                    except (ValueError, TypeError):
                        continue
                elif field in integer_fields:
                    if isinstance(value, (datetime, date, time)):
                        continue
                    try:
                        setattr(practica, field, int(float(value)))
                    except (ValueError, TypeError):
                        continue
                else:
                    setattr(practica, field, str(value).strip())
            _sincronizar_datos_practica(practica, alumno)
            if carrera:
                alumno.carrera_id = carrera.id
                practica.carrera = carrera.nombre.upper()
            db.session.add(practica)
            cerrar_servicio_social_por_practicas(alumno)
            savepoint.commit()
            insertados += 1
        except Exception as e:
            savepoint.rollback()
            errores.append(f'Fila {fila_num}: {str(e)}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errores.append(f'Error al guardar en base de datos: {str(e)}')
        insertados = duplicados = 0

    return {'insertados': insertados, 'duplicados': duplicados, 'errores': errores}

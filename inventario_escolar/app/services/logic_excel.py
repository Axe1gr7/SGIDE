import re
import unicodedata

import pandas as pd
from app.extensions import db
from app.models import Alumno, Carrera, Dependencia
from app.services.logic_expediente import registrar_alumno

# Hojas de plantilla/catálogo que no contienen alumnos
SHEETS_SKIP = {'BLANCO', 'CORREOS', 'CATALOGO', 'CATALOGOS'}

# Mapeo de nombres de hoja Excel -> nombre de carrera en BD
SHEET_CARRERA = {
    'LOGISTICA': 'Logística',
    'BIOTECNOLOGIA': 'Biotecnología',
    'PGA': 'PGA',
    'PROGRAMACIÓN': 'Programación',
    'PROGRAMACION': 'Programación',
    'MECATRÓNICA': 'Mecatrónica',
    'MECATRONICA': 'Mecatrónica',
}

# Alias de especialidad -> nombre de carrera en BD
CARRERA_ALIASES = {
    'logistica': 'Logística',
    'biotecnologia': 'Biotecnología',
    'pga': 'PGA',
    'procesos de gestion administrativa': 'PGA',
    'programacion': 'Programación',
    'mecatronica': 'Mecatrónica',
}

# Mapeo flexible de posibles nombres de columna (español/inglés y variantes)
COLUMN_MAP = {
    'nombre': [
        'nombre', 'nombre_del_alumno', 'name', 'nombre_alumno', 'alumno',
        'nombre_completo', 'nombre completo',
    ],
    'matricula': [
        'matricula', 'numero_de_control', 'numero_de__control', 'num_de_control',
        'no_control', 'matricula_del_alumno', 'numero_de_control_del_alumno',
        'num_control', 'clave_unica',
    ],
    'carrera': [
        'carrera', 'especialidad', 'programa', 'programa_educativo', 'area',
        'carrera_del_alumno',
    ],
    'anio_generacion': [
        'anio_generacion', 'anio_ingreso', 'generacion', 'anio_de_generacion',
        'anio_inicio', 'anio_de_ingreso', 'año_de_generacion', 'año_de_ingreso',
        'año_1', 'ano_1', 'anio_1',
    ],
    'anio_egreso': [
        'anio_egreso', 'año_2', 'ano_2', 'anio_2', 'anio_fin', 'anio_termino',
        'año_egreso', 'año_fin', 'año_termino',
    ],
    'estatus': ['estatus', 'status', 'estado', 'situacion'],
    'sector': ['sector'],
    'dependencia': [
        'institucion_prestataria', 'institucion', 'dependencia', 'lugar', 'empresa',
        'institucion_prestadora', 'dependencia_social',
    ],
}


def _normalize_text(text):
    """Normaliza texto: minúsculas, sin acentos, espacios/puntos unificados."""
    if text is None:
        return ''
    text = str(text).strip().lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('.', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _normalize_columns(df):
    """Normaliza los nombres de columna para comparación flexible."""
    df.columns = [_normalize_text(col).replace(' ', '_') for col in df.columns]
    df.columns = [re.sub(r'_+', '_', col).strip('_') for col in df.columns]


def _find_column(df, campo):
    """Encuentra la columna real para un campo dado, o None si no existe."""
    for candidato in COLUMN_MAP[campo]:
        norm = _normalize_text(candidato).replace(' ', '_')
        norm = re.sub(r'_+', '_', norm).strip('_')
        if norm in df.columns:
            return norm
    return None


def _format_matricula(val):
    """Convierte matrícula/número de control a string sin perder dígitos."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, float):
        return str(int(val))
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s or None


def _get_value(row, col, default=None, converter=None):
    """Obtiene un valor de la fila de forma segura, manejando NaN y valores vacíos."""
    if col is None:
        return default
    val = row[col]
    if pd.isna(val):
        return default
    if converter:
        try:
            result = converter(val)
            if isinstance(result, str) and result.strip() == '':
                return default
            return result
        except (ValueError, TypeError):
            return default
    return val


def _parse_anio(val):
    """Convierte un valor a año de 2 dígitos (ej: 2024 -> 24, 18 -> 18)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        num = int(float(val))
    except (ValueError, TypeError):
        return None
    if num >= 2000:
        return num % 100
    if 0 <= num <= 99:
        return num
    return num % 100


def _anio_from_matricula(matricula):
    """Extrae año de generación de los primeros 2 dígitos del número de control."""
    if not matricula or len(matricula) < 2:
        return None
    prefix = matricula[:2]
    if prefix.isdigit():
        return int(prefix)
    return None


def _resolve_carrera(carrera_val, sheet_name=None):
    """Busca la carrera por valor de celda, alias o nombre de hoja."""
    if carrera_val is not None and not (isinstance(carrera_val, float) and pd.isna(carrera_val)):
        if isinstance(carrera_val, (int, float)) and not pd.isna(carrera_val):
            carrera = Carrera.query.filter_by(prefijo_id=int(carrera_val), is_deleted=False).first()
            if carrera:
                return carrera

        nombre_raw = str(carrera_val).strip()
        if nombre_raw:
            carrera = Carrera.query.filter_by(nombre=nombre_raw, is_deleted=False).first()
            if carrera:
                return carrera

            alias_key = _normalize_text(nombre_raw)
            alias_nombre = CARRERA_ALIASES.get(alias_key)
            if alias_nombre:
                carrera = Carrera.query.filter_by(nombre=alias_nombre, is_deleted=False).first()
                if carrera:
                    return carrera

            carrera = Carrera.query.filter(
                Carrera.nombre.ilike(f'%{nombre_raw}%'),
                Carrera.is_deleted == False
            ).first()
            if carrera:
                return carrera

    if sheet_name:
        carrera_nombre = SHEET_CARRERA.get(sheet_name.strip().upper())
        if carrera_nombre:
            return Carrera.query.filter_by(nombre=carrera_nombre, is_deleted=False).first()

    return None


def _row_is_empty(row, cols):
    """Determina si una fila no tiene datos útiles de alumno."""
    nombre = _get_value(row, cols['nombre'], None, str)
    matricula = _format_matricula(_get_value(row, cols['matricula'], None))
    if nombre and str(nombre).strip():
        return False
    if matricula:
        return False
    return True


import re
import unicodedata

import pandas as pd
from app.extensions import db
from app.models import Alumno, Carrera, Dependencia, Expediente, Documento
from app.services.logic_expediente import registrar_alumno

# Hojas de plantilla/catálogo que no contienen alumnos
SHEETS_SKIP = {'BLANCO', 'CORREOS', 'CATALOGO', 'CATALOGOS'}

# Mapeo de nombres de hoja Excel -> nombre de carrera en BD
SHEET_CARRERA = {
    'LOGISTICA': 'Logística',
    'BIOTECNOLOGIA': 'Biotecnología',
    'PGA': 'PGA',
    'PROGRAMACIÓN': 'Programación',
    'PROGRAMACION': 'Programación',
    'MECATRÓNICA': 'Mecatrónica',
    'MECATRONICA': 'Mecatrónica',
}

# Alias de especialidad -> nombre de carrera en BD
CARRERA_ALIASES = {
    'logistica': 'Logística',
    'biotecnologia': 'Biotecnología',
    'pga': 'PGA',
    'procesos de gestion administrativa': 'PGA',
    'programacion': 'Programación',
    'mecatronica': 'Mecatrónica',
}

# Mapeo flexible de posibles nombres de columna (español/inglés y variantes)
COLUMN_MAP = {
    'nombre': [
        'nombre', 'nombre_del_alumno', 'name', 'nombre_alumno', 'alumno',
        'nombre_completo', 'nombre completo',
    ],
    'matricula': [
        'matricula', 'numero_de_control', 'numero_de__control', 'num_de_control',
        'no_control', 'matricula_del_alumno', 'numero_de_control_del_alumno',
        'num_control', 'clave_unica',
    ],
    'carrera': [
        'carrera', 'especialidad', 'programa', 'programa_educativo', 'area',
        'carrera_del_alumno',
    ],
    'anio_generacion': [
        'anio_generacion', 'anio_ingreso', 'generacion', 'anio_de_generacion',
        'anio_inicio', 'anio_de_ingreso', 'año_de_generacion', 'año_de_ingreso',
        'año_1', 'ano_1', 'anio_1',
    ],
    'anio_egreso': [
        'anio_egreso', 'año_2', 'ano_2', 'anio_2', 'anio_fin', 'anio_termino',
        'año_egreso', 'año_fin', 'año_termino',
    ],
    'estatus': ['estatus', 'status', 'estado', 'situacion'],
    'sector': ['sector'],
    'dependencia': [
        'institucion_prestataria', 'institucion', 'dependencia', 'lugar', 'empresa',
        'institucion_prestadora', 'dependencia_social',
    ],
}

# Mapeo de columnas normalizadas de documentos a su nombre oficial
DOC_COLUMNS_MAP = {
    'sol': 'SOL',
    'act_nacimiento': 'ACT. NACIMIENTO',
    'presentacion': 'PRESENTACIÓN',
    'aceptacion': 'ACEPTACIÓN',
    'tarjeta_de_control': 'TARJETA DE CONTROL',
    'trimestral': 'TRIMESTRAL',
    'final': 'FINAL',
    'terminacion': 'TERMINACIÓN',
    'liberacion': 'LIBERACIÓN',
    'acreditacion': 'ACREDITACIÓN'
}


def _normalize_text(text):
    """Normaliza texto: minúsculas, sin acentos, espacios/puntos unificados."""
    if text is None:
        return ''
    text = str(text).strip().lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('.', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _normalize_columns(df):
    """Normaliza los nombres de columna para comparación flexible."""
    df.columns = [_normalize_text(col).replace(' ', '_') for col in df.columns]
    df.columns = [re.sub(r'_+', '_', col).strip('_') for col in df.columns]


def _find_column(df, campo):
    """Encuentra la columna real para un campo dado, o None si no existe."""
    for candidato in COLUMN_MAP[campo]:
        norm = _normalize_text(candidato).replace(' ', '_')
        norm = re.sub(r'_+', '_', norm).strip('_')
        if norm in df.columns:
            return norm
    return None


def _format_matricula(val):
    """Convierte matrícula/número de control a string sin perder dígitos."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, float):
        return str(int(val))
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s or None


def _get_value(row, col, default=None, converter=None):
    """Obtiene un valor de la fila de forma segura, manejando NaN y valores vacíos."""
    if col is None:
        return default
    val = row[col]
    if pd.isna(val):
        return default
    if converter:
        try:
            result = converter(val)
            if isinstance(result, str) and result.strip() == '':
                return default
            return result
        except (ValueError, TypeError):
            return default
    return val


def _parse_anio(val):
    """Convierte un valor a año de 2 dígitos (ej: 2024 -> 24, 18 -> 18)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        num = int(float(val))
    except (ValueError, TypeError):
        return None
    if num >= 2000:
        return num % 100
    if 0 <= num <= 99:
        return num
    return num % 100


def _anio_from_matricula(matricula):
    """Extrae año de generación de los primeros 2 dígitos del número de control."""
    if not matricula or len(matricula) < 2:
        return None
    prefix = matricula[:2]
    if prefix.isdigit():
        return int(prefix)
    return None


def _resolve_carrera(carrera_val, sheet_name=None):
    """Busca la carrera por valor de celda, alias o nombre de hoja."""
    if carrera_val is not None and not (isinstance(carrera_val, float) and pd.isna(carrera_val)):
        if isinstance(carrera_val, (int, float)) and not pd.isna(carrera_val):
            carrera = Carrera.query.filter_by(prefijo_id=int(carrera_val), is_deleted=False).first()
            if carrera:
                return carrera

        nombre_raw = str(carrera_val).strip()
        if nombre_raw:
            carrera = Carrera.query.filter_by(nombre=nombre_raw, is_deleted=False).first()
            if carrera:
                return carrera

            alias_key = _normalize_text(nombre_raw)
            alias_nombre = CARRERA_ALIASES.get(alias_key)
            if alias_nombre:
                carrera = Carrera.query.filter_by(nombre=alias_nombre, is_deleted=False).first()
                if carrera:
                    return carrera

            carrera = Carrera.query.filter(
                Carrera.nombre.ilike(f'%{nombre_raw}%'),
                Carrera.is_deleted == False
            ).first()
            if carrera:
                return carrera

    if sheet_name:
        carrera_nombre = SHEET_CARRERA.get(sheet_name.strip().upper())
        if carrera_nombre:
            return Carrera.query.filter_by(nombre=carrera_nombre, is_deleted=False).first()

    return None


def _row_is_empty(row, cols):
    """Determina si una fila no tiene datos útiles de alumno."""
    nombre = _get_value(row, cols['nombre'], None, str)
    matricula = _format_matricula(_get_value(row, cols['matricula'], None))
    if nombre and str(nombre).strip():
        return False
    if matricula:
        return False
    return True


def _procesar_hoja(df, sheet_name, insertados, duplicados, errores, tipo_modulo='s'):
    """Procesa una hoja del Excel e inserta o actualiza alumnos."""
    _normalize_columns(df)

    cols = {
        'nombre': _find_column(df, 'nombre'),
        'matricula': _find_column(df, 'matricula'),
        'carrera': _find_column(df, 'carrera'),
        'anio': _find_column(df, 'anio_generacion'),
        'anio_egreso': _find_column(df, 'anio_egreso'),
        'estatus': _find_column(df, 'estatus'),
        'sector': _find_column(df, 'sector'),
        'dependencia': _find_column(df, 'dependencia'),
    }

    for idx, row in df.iterrows():
        fila_num = idx + 2
        etiqueta = f'{sheet_name} fila {fila_num}'

        if _row_is_empty(row, cols):
            continue

        try:
            with db.session.begin_nested():
                nombre = _get_value(row, cols['nombre'], None, str)
                if nombre:
                    nombre = nombre.strip() or None

                matricula = _format_matricula(_get_value(row, cols['matricula'], None))

                carrera_val = _get_value(row, cols['carrera'], None) if cols['carrera'] else None
                carrera = _resolve_carrera(carrera_val, sheet_name)

                anio = _get_value(row, cols['anio'], None) if cols['anio'] else None
                anio = _parse_anio(anio) if anio is not None else None
                if anio is None and matricula:
                    anio = _anio_from_matricula(matricula)

                anio_egreso = _get_value(row, cols['anio_egreso'], None) if cols['anio_egreso'] else None
                anio_egreso = _parse_anio(anio_egreso) if anio_egreso is not None else None

                estatus = _get_value(row, cols['estatus'], 'Activo', str)
                if estatus:
                    estatus = estatus.strip()
                else:
                    estatus = 'Activo'
                if estatus not in ('Activo', 'Inactivo', 'Egresado'):
                    estatus = 'Activo'

                alumno = None
                if matricula:
                    alumno = Alumno.query.filter_by(matricula=matricula, is_deleted=False).first()

                if alumno:
                    duplicados += 1
                    # Actualizar campos del alumno si vienen en el Excel y estaban vacíos
                    if nombre and not alumno.nombre:
                        alumno.nombre = nombre
                    if carrera and not alumno.carrera_id:
                        alumno.carrera_id = carrera.id
                    if anio and not alumno.anio_generacion:
                        alumno.anio_generacion = anio
                    if anio_egreso and not alumno.anio_egreso:
                        alumno.anio_egreso = anio_egreso
                    db.session.add(alumno)
                    db.session.flush()
                else:
                    carrera_id = carrera.id if carrera else None
                    carrera_prefijo = carrera.prefijo_id if carrera else None
                    alumno, expedientes = registrar_alumno(
                        nombre=nombre,
                        matricula=matricula,
                        anio_generacion=anio,
                        carrera_id=carrera_id,
                        carrera_prefijo=carrera_prefijo,
                        anio_egreso=anio_egreso,
                        estatus=estatus,
                    )
                    insertados += 1

                # Recuperar o asignar expediente del tipo seleccionado
                expediente = Expediente.query.filter_by(
                    alumno_id=alumno.id,
                    tipo_modulo=tipo_modulo,
                    is_deleted=False
                ).first()

                if expediente:
                    sector = _get_value(row, cols['sector'], None, str)
                    if sector:
                        sector = sector.strip()
                    dep_nombre = _get_value(row, cols['dependencia'], None, str)
                    if dep_nombre:
                        dep_nombre = dep_nombre.strip()

                    if sector:
                        expediente.sector = sector
                    if dep_nombre:
                        dep = Dependencia.query.filter(
                            Dependencia.nombre.ilike(f'%{dep_nombre}%'),
                            Dependencia.is_deleted == False
                        ).first()
                        if not dep:
                            dep_tipo = 'Servicio' if tipo_modulo == 's' else 'Practicas'
                            dep = Dependencia(nombre=dep_nombre, tipo=dep_tipo, sector=sector)
                            db.session.add(dep)
                            db.session.flush()
                        expediente.dependencia_id = dep.id
                        if dep.sector and not expediente.sector:
                            expediente.sector = dep.sector

                    # Inyección de documentos del expediente
                    for norm_col, doc_name in DOC_COLUMNS_MAP.items():
                        if norm_col in df.columns:
                            val = row[norm_col]
                            if pd.notna(val):
                                str_val = str(val).strip().lower()
                                if str_val in ('1', '1.0', 'entregado'):
                                    estado = 'Entregado'
                                elif str_val in ('2', '2.0', 'recibido'):
                                    estado = 'Recibido'
                                elif str_val in ('0', '0.0', 'no realizado', 'no_realizado'):
                                    estado = 'No Realizado'
                                else:
                                    estado = 'Entregado'
                            else:
                                estado = 'Pendiente'

                            # Crear o actualizar documento
                            doc = Documento.query.filter_by(
                                expediente_id=expediente.id,
                                nombre_formato=doc_name,
                                is_deleted=False
                            ).first()
                            if doc:
                                doc.estado = estado
                            else:
                                doc = Documento(
                                    expediente_id=expediente.id,
                                    nombre_formato=doc_name,
                                    estado=estado
                                )
                                db.session.add(doc)

        except Exception as e:
            errores.append(f'{etiqueta}: {str(e)}')

    return insertados, duplicados, errores


def procesar_excel(filepath, tipo_modulo='s'):
    """
    Importa alumnos desde un archivo Excel de forma flexible.
    Soporta archivos con múltiples hojas (una por especialidad), como el formato
    institucional de Servicio Social con columnas:
      NOMBRE DEL ALUMNO, NUMERO DE CONTROL, ESPECIALIDAD, INSTITUCIÓN PRESTATARIA, SECTOR, etc.

    Returns dict: {insertados: int, duplicados: int, errores: list[str], hojas: list[str]}
    """
    try:
        xl = pd.ExcelFile(filepath, engine='openpyxl')
    except Exception as e:
        return {
            'insertados': 0,
            'duplicados': 0,
            'errores': [f'Error al leer el archivo: {str(e)}'],
            'hojas': [],
        }

    insertados = 0
    duplicados = 0
    errores = []
    hojas_procesadas = []

    for sheet_name in xl.sheet_names:
        if sheet_name.strip().upper() in SHEETS_SKIP:
            continue

        try:
            df = pd.read_excel(xl, sheet_name=sheet_name, engine='openpyxl')
        except Exception as e:
            errores.append(f'Hoja "{sheet_name}": error al leer ({str(e)})')
            continue

        if df.empty:
            continue

        insertados, duplicados, errores = _procesar_hoja(
            df, sheet_name, insertados, duplicados, errores, tipo_modulo=tipo_modulo
        )
        hojas_procesadas.append(sheet_name)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errores.append(f'Error al guardar los registros: {str(e)}')
        insertados = 0

    return {
        'insertados': insertados,
        'duplicados': duplicados,
        'errores': errores,
        'hojas': hojas_procesadas,
    }


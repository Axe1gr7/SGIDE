import os
import re
import unicodedata
import zipfile
from io import BytesIO

from app.extensions import db
from app.models import Alumno, Expediente, Documento
from app.services.file_manager import guardar_documento_datos

# Mapeo de palabras clave a nombres oficiales de formatos
DOC_KEYWORDS = {
    'SOL': ['sol', 'solicitud'],
    'ACT. NACIMIENTO': ['acta', 'nacimiento', 'act_nac', 'nac'],
    'PRESENTACIÓN': ['presentacion', 'presenta', 'pres'],
    'ACEPTACIÓN': ['aceptacion', 'acepta', 'acep'],
    'TARJETA DE CONTROL': ['tarjeta', 'control', 'tarj'],
    'TRIMESTRAL': ['trimestral', 'trim', 'reporte_1', 'reporte_2', 'reporte_3', 'reporte1', 'reporte2', 'reporte3'],
    'FINAL': ['final', 'rep_final', 'reporte_final'],
    'TERMINACIÓN': ['terminacion', 'termina', 'term'],
    'LIBERACIÓN': ['liberacion', 'libera', 'lib'],
    'ACREDITACIÓN': ['acreditacion', 'acredita', 'acre']
}

def _normalizar_nombre_archivo(filename):
    """Limpia el nombre del archivo para la comparación (minúsculas, sin acentos)."""
    text = filename.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text

def _detectar_documento(nombre_normalizado):
    """Detecta qué formato/documento es basándose en palabras clave."""
    # Buscar coincidencia exacta o palabra clave
    for doc_name, keywords in DOC_KEYWORDS.items():
        for kw in keywords:
            # Buscar la palabra clave delimitada por caracteres no alfanuméricos
            pattern = rf'(?:^|[^a-z]){re.escape(kw)}(?:$|[^a-z])'
            if re.search(pattern, nombre_normalizado):
                return doc_name
    return None

def procesar_zip_pdfs(zip_file_stream, tipo_modulo='s'):
    """
    Procesa un archivo ZIP que contiene múltiples PDFs.
    Asigna cada PDF al expediente del alumno correspondiente.
    
    Returns dict: {
        'asignados': int,
        'no_asignados': int,
        'errores': list[str],
        'detalles': list[dict] # {archivo, alumno, doc, estado, error}
    }
    """
    resultado = {
        'asignados': 0,
        'no_asignados': 0,
        'errores': [],
        'detalle': []
    }
    
    try:
        # Cargar todos los alumnos activos en memoria para búsquedas eficientes
        alumnos = Alumno.query.filter_by(is_deleted=False).all()
        # Mapear matrículas y expedientes bases normalizados para coincidir rápido
        mapa_alumnos = []
        for a in alumnos:
            exp_norm = _normalizar_nombre_archivo(a.expediente_base) if a.expediente_base else ""
            exp_clean = exp_norm.replace("-", "").replace("_", "")
            mapa_alumnos.append({
                'alumno': a,
                'matricula': a.matricula.strip() if a.matricula else None,
                'expediente_base': exp_norm,
                'expediente_clean': exp_clean
            })
            
        with zipfile.ZipFile(BytesIO(zip_file_stream.read())) as z:
            for zip_info in z.infolist():
                if zip_info.is_dir():
                    continue
                
                filename = os.path.basename(zip_info.filename)
                if not filename or not filename.lower().endswith('.pdf'):
                    continue
                
                norm_name = _normalizar_nombre_archivo(filename)
                
                # 1. Emparejar con alumno
                alumno_matched = None
                for ma in mapa_alumnos:
                    # Coincidencia por matrícula
                    if ma['matricula'] and ma['matricula'] in norm_name:
                        alumno_matched = ma['alumno']
                        break
                    # Coincidencia por expediente base (ej: '24-4031' o '244031')
                    if ma['expediente_base'] and (ma['expediente_base'] in norm_name or ma['expediente_clean'] in norm_name):
                        alumno_matched = ma['alumno']
                        break
                        
                if not alumno_matched:
                    resultado['no_asignados'] += 1
                    resultado['detalle'].append({
                        'archivo': filename,
                        'alumno': None,
                        'tipo_doc': None,
                        'ok': False,
                        'error': 'No se encontró un alumno con esa matrícula o expediente base en el nombre de archivo.'
                    })
                    continue
                
                # 2. Emparejar con documento
                doc_name = _detectar_documento(norm_name)
                if not doc_name:
                    resultado['no_asignados'] += 1
                    resultado['detalle'].append({
                        'archivo': filename,
                        'alumno': alumno_matched.nombre,
                        'tipo_doc': None,
                        'ok': False,
                        'error': 'No se pudo identificar el tipo de documento (SOL, ACTA, etc.) en el nombre de archivo.'
                    })
                    continue
                
                # 3. Obtener el expediente del alumno
                expediente = Expediente.query.filter_by(
                    alumno_id=alumno_matched.id,
                    tipo_modulo=tipo_modulo,
                    is_deleted=False
                ).first()
                
                if not expediente:
                    resultado['no_asignados'] += 1
                    resultado['detalle'].append({
                        'archivo': filename,
                        'alumno': alumno_matched.nombre,
                        'tipo_doc': doc_name,
                        'ok': False,
                        'error': f'El alumno no cuenta con expediente de tipo "{tipo_modulo}".'
                    })
                    continue
                
                # 4. Guardar archivo y registrar en BD
                try:
                    with db.session.begin_nested():
                        file_data = z.read(zip_info.filename)
                        
                        # Nombre estandarizado: {clave_expediente}_{nombre_documento_limpio}.pdf
                        doc_name_clean = _normalizar_nombre_archivo(doc_name).replace(" ", "_")
                        new_filename = f"{expediente.clave_expediente}_{doc_name_clean}.pdf"
                        
                        # Guardar archivo físico
                        ruta_archivo = guardar_documento_datos(expediente, file_data, new_filename)
                        
                        # Buscar o crear documento
                        doc = Documento.query.filter_by(
                            expediente_id=expediente.id,
                            nombre_formato=doc_name,
                            is_deleted=False
                        ).first()
                        
                        if doc:
                            doc.estado = 'Entregado'
                            doc.ruta_archivo = ruta_archivo
                        else:
                            doc = Documento(
                                expediente_id=expediente.id,
                                nombre_formato=doc_name,
                                estado='Entregado',
                                ruta_archivo=ruta_archivo
                            )
                            db.session.add(doc)
                            
                    resultado['asignados'] += 1
                    resultado['detalle'].append({
                        'archivo': filename,
                        'alumno': alumno_matched.nombre,
                        'tipo_doc': doc_name,
                        'ok': True
                    })
                except Exception as e:
                    resultado['no_asignados'] += 1
                    resultado['detalle'].append({
                        'archivo': filename,
                        'alumno': alumno_matched.nombre,
                        'tipo_doc': doc_name,
                        'ok': False,
                        'error': str(e)
                    })
                    resultado['errores'].append(f"Archivo {filename}: {str(e)}")
                    
        # Commit general de las asignaciones exitosas
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        resultado['errores'].append(f"Error procesando el archivo ZIP: {str(e)}")
        
    return resultado

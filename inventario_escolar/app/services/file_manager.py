import os
import re
from flask import current_app
from werkzeug.utils import secure_filename

def _limpiar_nombre(nombre):
    """Limpia una cadena para hacerla segura para nombres de carpetas/archivos."""
    # Eliminar caracteres no deseados
    seguro = secure_filename(nombre)
    if not seguro:
        # En caso de que secure_filename borre todo (ej. caracteres especiales raros)
        seguro = re.sub(r'[^a-zA-Z0-9_-]', '_', nombre)
    return seguro

def _anio_completo(anio):
    """Convierte un año de 2 dígitos a 4 dígitos (ej. 18 -> 2018)."""
    try:
        anio = int(anio)
    except (TypeError, ValueError):
        return str(anio)
    if anio < 100:
        return str(2000 + anio)
    return str(anio)

def generar_ruta_relativa_expediente(expediente):
    """
    Genera la ruta relativa estructurada para un expediente:
    documentos/<apartado>/<anio>/<carrera>/<matricula_nombre>/<clave_expediente>
    """
    # Apartados (módulos) con subcarpetas por año
    modulo_nombres = {
        'p': 'practicas',
        's': 'servicio',
        'v': 'vinculacion'
    }
    apartado = modulo_nombres.get(expediente.tipo_modulo, 'otros')

    alumno = expediente.alumno
    carrera = _limpiar_nombre(alumno.carrera.nombre)
    # Subcarpeta por año completo de la generación (ej. 2018)
    anio = _anio_completo(alumno.anio_generacion)

    matricula = _limpiar_nombre(alumno.matricula)
    nombre = _limpiar_nombre(alumno.nombre)
    alumno_carpeta = f"{matricula}_{nombre}"

    clave_exp = _limpiar_nombre(expediente.clave_expediente)

    # Retorna: documentos/practicas/2018/Programacion/1234_Juan_Perez/EXP_001
    return os.path.join('documentos', apartado, anio, carrera, alumno_carpeta, clave_exp)

def guardar_documento(expediente, archivo, custom_filename=None):
    """
    Guarda un archivo de FileStorage en la estructura generada.
    Crea las carpetas si no existen.
    Devuelve la ruta relativa que debe guardarse en la BD.
    """
    if not archivo and not custom_filename:
        return None

    ruta_relativa = generar_ruta_relativa_expediente(expediente)
    ruta_absoluta_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], ruta_relativa)

    os.makedirs(ruta_absoluta_dir, exist_ok=True)

    if custom_filename:
        filename = custom_filename
    else:
        filename = secure_filename(archivo.filename)

    ruta_absoluta_archivo = os.path.join(ruta_absoluta_dir, filename)

    if archivo:
        archivo.save(ruta_absoluta_archivo)

    return os.path.join(ruta_relativa, filename)

def guardar_documento_datos(expediente, contenido_bytes, filename):
    """
    Guarda el contenido en bytes directamente en la estructura del expediente.
    Crea las carpetas si no existen y retorna la ruta relativa para guardar en BD.
    """
    ruta_relativa = generar_ruta_relativa_expediente(expediente)
    ruta_absoluta_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], ruta_relativa)
    os.makedirs(ruta_absoluta_dir, exist_ok=True)

    filename_limpio = secure_filename(filename)
    ruta_absoluta_archivo = os.path.join(ruta_absoluta_dir, filename_limpio)

    with open(ruta_absoluta_archivo, 'wb') as f:
        f.write(contenido_bytes)

    return os.path.join(ruta_relativa, filename_limpio)

def obtener_ruta_absoluta(ruta_relativa):
    """Obtiene la ruta absoluta en el sistema dado el path relativo guardado en la BD."""
    if not ruta_relativa:
        return None
    return os.path.join(current_app.config['UPLOAD_FOLDER'], ruta_relativa)


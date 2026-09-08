from app.extensions import db
import unicodedata

from app.models import Alumno, Expediente, Documento, Practica, Carrera

DOCUMENTOS_SERVICIO_SOCIAL = (
    'FSS2 carta de presentacion',
    'FSS4 Carta de aceptacion',
    'FSS8 Constancia terminacion de ss',
)


def _clave_carrera(valor):
    texto = '' if valor is None else str(valor).strip().lower()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return ''.join(c for c in texto if c.isalnum())


def resolver_carrera_practicas(valor):
    """Resuelve carreras del Excel de Prácticas tolerando acentos y variantes."""
    clave = _clave_carrera(valor)
    aliases = {
        'logistica': 'Logística',
        'biotecnologia': 'Biotecnología',
        'pga': 'PGA',
        'procesosdegestionadministrativa': 'PGA',
        'programacion': 'Programación',
        'mecatronica': 'Mecatrónica',
    }
    if clave.startswith('5t0') or clave.startswith('6t0'):
        clave = clave[3:]
        if clave.startswith('meca'):
            clave = 'mecatronica'
        elif clave.startswith('bio'):
            clave = 'biotecnologia'
        elif clave.startswith('log'):
            clave = 'logistica'
        elif clave.startswith('prog'):
            clave = 'programacion'
        elif clave.startswith('pga'):
            clave = 'pga'
    nombre = aliases.get(clave)
    if not nombre:
        return None
    return Carrera.query.filter_by(nombre=nombre, is_deleted=False).first()


def sincronizar_carreras_practicas():
    """Completa la carrera de alumnos vinculados a prácticas activas."""
    registros = Practica.query.filter(
        Practica.is_deleted == False,
        Practica.alumno_id != None,
        db.or_(Practica.carrera != None, Practica.grado_carrera != None),
    ).all()
    actualizados = 0
    for practica in registros:
        carrera = resolver_carrera_practicas(practica.carrera or practica.grado_carrera)
        if carrera and practica.alumno.carrera_id != carrera.id:
            practica.alumno.carrera_id = carrera.id
            actualizados += 1
    return actualizados

def generar_expediente_base(anio_generacion, carrera_prefijo):
    """
    Generates base expediente ID.
    Example: anio=2024, prefijo=4 (Logística)
    Count existing alumnos with same anio+carrera, add 1, format to 3 digits.
    Result: '24-4031' where 24=year, 4=carrera, 031=consecutive
    """
    anio_sufijo = str(anio_generacion)[-2:]  # 2024 -> '24'
    
    # Prefix matching pattern
    prefix = f"{anio_sufijo}-{carrera_prefijo}"
    existing = Alumno.query.filter(
        Alumno.expediente_base.like(f"{prefix}%"),
        Alumno.is_deleted == False
    ).all()
    
    if existing:
        max_consecutivo = 0
        for a in existing:
            # a.expediente_base is like '24-4031'
            parte_num = a.expediente_base.split('-')[1]  # '4031'
            consecutivo = int(parte_num[1:])  # '031' -> 31
            if consecutivo > max_consecutivo:
                max_consecutivo = consecutivo
        consecutivo = max_consecutivo + 1
    else:
        consecutivo = 1
    
    expediente_base = f"{anio_sufijo}-{carrera_prefijo}{consecutivo:03d}"
    return expediente_base

def crear_expedientes_alumno(alumno):
    """
    Creates 3 Expediente records for an Alumno (p-, s-, v-).
    El commit se hace en el llamador para mantener la transacción atómica.
    """
    expedientes = []
    for tipo in ['p', 's', 'v']:
        clave = f"{tipo}-{alumno.expediente_base}"
        exp = Expediente(
            alumno_id=alumno.id,
            tipo_modulo=tipo,
            clave_expediente=clave
        )
        expedientes.append(exp)
    db.session.add_all(expedientes)
    return expedientes

def registrar_alumno(nombre=None, matricula=None, anio_generacion=None, carrera_id=None, carrera_prefijo=None,
                     anio_egreso=None, estatus='Activo'):
    """
    Full registration: create Alumno + 3 Expedientes.
    Acepta valores faltantes (None) para registrar alumnos incompletos
    que se completarán después mediante el formulario de edición.
    Returns (alumno, expedientes) tuple.
    """
    # Check duplicate (solo si hay matrícula)
    if matricula:
        existente = Alumno.query.filter_by(matricula=matricula, is_deleted=False).first()
        if existente:
            raise ValueError(f'La matrícula {matricula} ya está registrada.')
    
    # Generar expediente_base temporal si faltan datos para la clave
    expediente_base = None
    if anio_generacion and carrera_prefijo:
        expediente_base = generar_expediente_base(anio_generacion, carrera_prefijo)
    else:
        # Clave temporal: 'TMP-<secuencia global>'
        ultimo = Alumno.query.filter(Alumno.expediente_base.like('TMP-%')).order_by(Alumno.id.desc()).first()
        consec = 1
        if ultimo and ultimo.expediente_base:
            try:
                consec = int(ultimo.expediente_base.split('-')[1]) + 1
            except (ValueError, IndexError):
                consec = 1
        expediente_base = f'TMP-{consec:04d}'
    
    alumno = Alumno(
        nombre=nombre,
        matricula=matricula,
        anio_generacion=anio_generacion,
        anio_egreso=anio_egreso,
        estatus=estatus,
        carrera_id=carrera_id,
        expediente_base=expediente_base
    )
    db.session.add(alumno)
    db.session.flush()  # Get the ID
    
    expedientes = crear_expedientes_alumno(alumno)
    return alumno, expedientes


def cerrar_servicio_social_por_practicas(alumno):
    """Cierra Servicio Social cuando existe una práctica profesional activa."""
    expediente = Expediente.query.filter_by(
        alumno_id=alumno.id,
        tipo_modulo='s',
        is_deleted=False,
    ).first()
    if expediente is None:
        expediente = Expediente(
            alumno_id=alumno.id,
            tipo_modulo='s',
            clave_expediente=f's-{alumno.expediente_base}',
        )
        db.session.add(expediente)
        db.session.flush()

    for nombre_formato in DOCUMENTOS_SERVICIO_SOCIAL:
        documento = Documento.query.filter_by(
            expediente_id=expediente.id,
            nombre_formato=nombre_formato,
            is_deleted=False,
        ).first()
        if documento is None:
            documento = Documento(
                expediente_id=expediente.id,
                nombre_formato=nombre_formato,
            )
            db.session.add(documento)
        documento.estado = 'Entregado'

    return expediente


def sincronizar_servicio_social_con_practicas():
    """Sincroniza alumnos existentes que ya tienen prácticas activas."""
    alumnos = (
        Alumno.query.join(Alumno.practicas)
        .filter(Alumno.is_deleted == False)
        .filter(Practica.is_deleted == False)
        .distinct()
        .all()
    )
    for alumno in alumnos:
        cerrar_servicio_social_por_practicas(alumno)
    return alumnos

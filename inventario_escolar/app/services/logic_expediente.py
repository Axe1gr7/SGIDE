from app.extensions import db
from app.models import Alumno, Expediente

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

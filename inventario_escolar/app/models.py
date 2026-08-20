from datetime import datetime, timezone
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.nombre}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return not self.is_deleted

    def __repr__(self):
        return f'<User {self.username}>'

class Carrera(db.Model):
    __tablename__ = 'carreras'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    prefijo_id = db.Column(db.Integer, unique=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    alumnos = db.relationship('Alumno', backref='carrera', lazy='dynamic')

    def __repr__(self):
        return f'<Carrera {self.nombre} ({self.prefijo_id})>'

class Alumno(db.Model):
    __tablename__ = 'alumnos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=True)
    matricula = db.Column(db.String(50), nullable=True)
    anio_generacion = db.Column(db.Integer, nullable=True)  # Año de inicio (2 dígitos, ej. 18)
    anio_egreso = db.Column(db.Integer, nullable=True)       # Año de fin (2 dígitos, ej. 21)
    estatus = db.Column(db.String(20), nullable=False, default='Activo')  # Activo / Inactivo / Egresado
    carrera_id = db.Column(db.Integer, db.ForeignKey('carreras.id'), nullable=True)
    expediente_base = db.Column(db.String(20), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expedientes = db.relationship('Expediente', backref='alumno', lazy='dynamic')

    @property
    def generacion_completa(self):
        """Devuelve la generación completa, ej: '2018-2021'. Si falta el año, retorna 'Pendiente'."""
        if not self.anio_generacion:
            return 'Pendiente'
        def full(anio):
            return anio if anio > 100 else 2000 + int(anio)
        inicio = full(self.anio_generacion)
        if self.anio_egreso:
            return f'{inicio}-{full(self.anio_egreso)}'
        return f'{inicio}'

    def __repr__(self):
        return f'<Alumno {self.nombre} [{self.expediente_base}]>'

class Dependencia(db.Model):
    __tablename__ = 'dependencias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='Ambos')  # Practicas / Servicio / Ambos
    sector = db.Column(db.String(30), nullable=True)  # Municipal / Estatal / Salud
    domicilio = db.Column(db.String(300), nullable=True)
    contacto = db.Column(db.String(150), nullable=True)
    telefono = db.Column(db.String(50), nullable=True)
    correo = db.Column(db.String(120), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expedientes = db.relationship('Expediente', backref='dependencia', lazy='dynamic')

    def __repr__(self):
        return f'<Dependencia {self.nombre}>'


class Expediente(db.Model):
    __tablename__ = 'expedientes'
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumnos.id'), nullable=False)
    tipo_modulo = db.Column(db.String(1), nullable=False)
    clave_expediente = db.Column(db.String(30), unique=True, nullable=False)
    sector = db.Column(db.String(30), nullable=True)  # Dependencias Servicio Social: Municipal / Estatal / Salud
    dependencia_id = db.Column(db.Integer, db.ForeignKey('dependencias.id'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    documentos = db.relationship('Documento', backref='expediente', lazy='dynamic')

    def __repr__(self):
        return f'<Expediente {self.clave_expediente}>'

class Documento(db.Model):
    __tablename__ = 'documentos'
    id = db.Column(db.Integer, primary_key=True)
    expediente_id = db.Column(db.Integer, db.ForeignKey('expedientes.id'), nullable=False)
    nombre_formato = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default='Pendiente')
    ruta_archivo = db.Column(db.String(500), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Documento {self.nombre_formato} [{self.estado}]>'


# ── Módulos de Vinculación ──────────────────────────────────────────────────

class ModuloVinculacion(db.Model):
    __tablename__ = 'modulos_vinculacion'
    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    icono       = db.Column(db.String(80), nullable=True, default='fa-folder')
    color       = db.Column(db.String(30), nullable=True, default='#4f46e5')
    orden       = db.Column(db.Integer, default=0)
    is_deleted  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    submodulos  = db.relationship('SubModuloVinculacion', backref='modulo',
                                  lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ModuloVinculacion {self.nombre}>'


class SubModuloVinculacion(db.Model):
    __tablename__ = 'submodulos_vinculacion'
    id         = db.Column(db.Integer, primary_key=True)
    modulo_id  = db.Column(db.Integer, db.ForeignKey('modulos_vinculacion.id'), nullable=False)
    nombre     = db.Column(db.String(200), nullable=False)
    descripcion= db.Column(db.Text, nullable=True)
    icono      = db.Column(db.String(80), nullable=True, default='fa-folder-open')
    orden      = db.Column(db.Integer, default=0)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    archivos   = db.relationship('ArchivoSubModulo', backref='submodulo',
                                 lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<SubModuloVinculacion {self.nombre}>'


class ArchivoSubModulo(db.Model):
    __tablename__ = 'archivos_submodulo'
    id           = db.Column(db.Integer, primary_key=True)
    submodulo_id = db.Column(db.Integer, db.ForeignKey('submodulos_vinculacion.id'), nullable=False)
    nombre       = db.Column(db.String(200), nullable=False)
    descripcion  = db.Column(db.Text, nullable=True)
    ruta_archivo = db.Column(db.String(500), nullable=True)
    tipo_archivo = db.Column(db.String(50), nullable=True)   # pdf, docx, xlsx, …
    is_deleted   = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ArchivoSubModulo {self.nombre}>'


# ── Módulo de Prácticas Profesionales ──────────────────────────────────────

class Practica(db.Model):
    """
    Tabla dedicada exclusivamente al módulo de Prácticas Profesionales.
    La estructura de campos refleja exactamente los encabezados del archivo
    PRACTICAS_1.xlsx para permitir importación masiva sin pérdida de información.
    """
    __tablename__ = 'practicas'

    # ── Listas de valores válidos para campos selectores ───────────────────
    GRADOS_CARRERA = [
        '5T0-MECA-AMBI', '5T0-MECA-BM', '5T0-MECA-AV', '5T0-MECA-BV',
        '5T0-BIO-AM',    '5T0-BIO-AV',
        '5T0-LOG-AM',    '5T0-LOG-AV',
        '5T0-PROG-AM',   '5T0-PROG-AV',
        '5T0-PGA-AM',    '5T0-PGA-AV',
        '6T0-MECA-AMBI', '6T0-MECA-BM', '6T0-MECA-AV', '6T0-MECA-BV',
        '6T0-BIO-AM',    '6T0-BIO-AV',
        '6T0-LOG-AM',    '6T0-LOG-AV',
        '6T0-PROG-AM',   '6T0-PROG-AV',
        '6T0-PGA-AM',    '6T0-PGA-AV',
    ]
    TURNOS         = ['MATUTINO', 'VESPERTINO']
    CARRERAS       = ['MECATRÓNICA', 'BIOTECNOLOGÍA', 'LOGÍSTICA', 'PROGRAMACIÓN']
    OBSERVACIONES_OPTS = ['CONCLUIDO', 'EN TRÁMITE']
    PROCESOS       = ['EMPRESA', 'INSTITUCIÓN', 'PROYECTO', 'DUAL', 'CERTIFICACIÓN']
    SECTORES       = [
        'SECTOR PÚBLICO', 'MICROEMPRESAS', 'PEQUEÑAS EMPRESAS',
        'MEDIANAS EMPRESAS', 'GRANDES EMPRESAS',
        'SECTOR SOCIAL', 'ORGANIZACIONES DE LA SOCIEDAD CIVIL',
    ]
    SEXOS          = ['HOMBRE', 'MUJER']
    OPTS_SNC       = ['SI', 'NO', 'CORREGIR']   # SI / NO / CORREGIR
    ESTADOS        = ['ENTREGADO', 'ATRASADO']

    # ── Clave primaria del sistema ─────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── Columna 1: No. REGISTRO ────────────────────────────────────────────
    no_registro = db.Column(db.Integer, nullable=True)

    # ── Columna 2: CONSECUTIVO ─────────────────────────────────────────────
    consecutivo = db.Column(db.Integer, nullable=True)

    # ── Columna 3: No. CONSTANCIA ─────────────────────────────────────────
    # Ej: PC06/MATUTINO/002/2026
    no_constancia = db.Column(db.String(50), nullable=True)

    # ── Columna 4: NOMBRE ─────────────────────────────────────────────────
    nombre = db.Column(db.String(250), nullable=True)

    # ── Columna 5: Nombre Minusculas ──────────────────────────────────────
    nombre_minusculas = db.Column(db.String(250), nullable=True)

    # ── Columna 6: MATRÍCULA ──────────────────────────────────────────────
    matricula = db.Column(db.String(50), nullable=True, index=True)

    # ── Columna 7: TELÉFONO ───────────────────────────────────────────────
    telefono = db.Column(db.String(20), nullable=True)

    # ── Columna 8: CORREO ESTUDIANTE ──────────────────────────────────────
    correo_estudiante = db.Column(db.String(150), nullable=True)

    # ── Columna 9: GRADO-CARRERA (selector) ──────────────────────────────
    # Valores: GRADOS_CARRERA
    grado_carrera = db.Column(db.String(30), nullable=True)

    # ── Columna 10: TURNO (selector) ─────────────────────────────────────
    # Valores: TURNOS
    turno = db.Column(db.String(15), nullable=True)

    # ── Columna 11: CARRERA (selector) ───────────────────────────────────
    # Valores: CARRERAS
    carrera = db.Column(db.String(50), nullable=True)

    # ── Columna 12: OBSERVACIONES (selector) ─────────────────────────────
    # Valores: OBSERVACIONES_OPTS
    observaciones = db.Column(db.String(20), nullable=True)

    # ── Columna 13: PROCESO (selector) ───────────────────────────────────
    # Valores: PROCESOS
    proceso = db.Column(db.String(30), nullable=True)

    # ── Columna 14: EMPRESA ───────────────────────────────────────────────
    empresa = db.Column(db.String(250), nullable=True)

    # ── Columna 15: SECTOR (selector) ────────────────────────────────────
    # Valores: SECTORES
    sector = db.Column(db.String(60), nullable=True)

    # ── Columna 16: NOMBRE DEL PROYECTO ──────────────────────────────────
    nombre_proyecto = db.Column(db.String(300), nullable=True)

    # ── Columna 17: TEL. EMPRESA ──────────────────────────────────────────
    tel_empresa = db.Column(db.String(20), nullable=True)

    # ── Columna 18: DIRECCIÓN EMPRESA ────────────────────────────────────
    direccion_empresa = db.Column(db.String(400), nullable=True)

    # ── Columna 19: CORR. EM ──────────────────────────────────────────────
    correo_empresa = db.Column(db.String(150), nullable=True)

    # ── Columna 20: GENERACIÓN ────────────────────────────────────────────
    # Ej: "23-26"
    generacion = db.Column(db.String(10), nullable=True)

    # ── Columna 21: H/M (selector) ───────────────────────────────────────
    # Valores: SEXOS
    sexo = db.Column(db.String(10), nullable=True)

    # ── Columna 22: BECADOS ───────────────────────────────────────────────
    # Ej: 1.00
    becados = db.Column(db.Numeric(10, 2), nullable=True)

    # ── Columna 23: MONTO ─────────────────────────────────────────────────
    # Puede ser numérico o "N/A"
    monto = db.Column(db.String(20), nullable=True)

    # ── Columnas 24-29: Solicitud de Prácticas ────────────────────────────
    # Columna 24: S. PRÁC (selector) — Valores: OPTS_SNC
    s_prac = db.Column(db.String(15), nullable=True)
    # Columna 25: S. PRÁC. — fecha serializada raw del Excel
    s_prac_fecha_excel = db.Column(db.Date, nullable=True)
    # Columna 26: F. INICIO — fecha de inicio de prácticas
    f_inicio = db.Column(db.Date, nullable=True)
    # Columna 27: DIA
    f_inicio_dia = db.Column(db.Integer, nullable=True)
    # Columna 28: MES
    f_inicio_mes = db.Column(db.String(15), nullable=True)
    # Columna 29: AÑO
    f_inicio_anio = db.Column(db.Integer, nullable=True)

    # ── Columnas 30-32: Carta de Presentación ────────────────────────────
    # Columna 30: C.PRES. (selector) — Valores: OPTS_SNC
    c_pres = db.Column(db.String(15), nullable=True)
    # Columna 31: C.PRES.2 — fecha serializada raw del Excel
    c_pres_fecha_excel = db.Column(db.Date, nullable=True)
    # Columna 32: F.C.P — fecha carta de presentación
    f_cp = db.Column(db.Date, nullable=True)

    # ── Columnas 33-38: Carta de Aceptación ──────────────────────────────
    # Columna 33: C. ACEP (selector) — Valores: OPTS_SNC
    c_acep = db.Column(db.String(15), nullable=True)
    # Columna 34: C. ACEP. — fecha serializada raw del Excel
    c_acep_fecha_excel = db.Column(db.Date, nullable=True)
    # Columna 35: F.C.A — fecha carta de aceptación
    f_ca = db.Column(db.Date, nullable=True)
    # Columna 36: DIA 3
    f_ca_dia = db.Column(db.Integer, nullable=True)
    # Columna 37: MES4
    f_ca_mes = db.Column(db.String(15), nullable=True)
    # Columna 38: AÑO 5
    f_ca_anio = db.Column(db.Integer, nullable=True)

    # ── Columnas 39-41: Plan de Trabajo ──────────────────────────────────
    # Columna 39: P. TRABJ (selector) — Valores: OPTS_SNC
    p_trabj = db.Column(db.String(15), nullable=True)
    # Columna 40: P. TRABJ. — fecha serializada raw del Excel
    p_trabj_fecha_excel = db.Column(db.Date, nullable=True)
    # Columna 41: F. P.TR — fecha plan de trabajo
    f_ptr = db.Column(db.Date, nullable=True)

    # ── Columnas 42-46: Informe Intermedio ───────────────────────────────
    # Columna 42: I. INTER (selector) — Valores: OPTS_SNC
    i_inter = db.Column(db.String(15), nullable=True)
    # Columna 43: I. INTER. — fecha serializada raw del Excel
    i_inter_fecha_excel = db.Column(db.Date, nullable=True)
    # Columna 44: F.I.I. — fecha informe intermedio
    f_ii = db.Column(db.Date, nullable=True)
    # Columna 45: F.L. I.I. — fecha límite informe intermedio
    f_l_ii = db.Column(db.Date, nullable=True)
    # Columna 46: ESTADO (selector) — Valores: ESTADOS
    estado = db.Column(db.String(15), nullable=True)

    # ── Columnas 47-50: Informe Final ─────────────────────────────────────
    # Columna 47: INF. FINAL (selector) — Valores: OPTS_SNC
    inf_final = db.Column(db.String(15), nullable=True)
    # Columna 48: INF. FINAL6 — valor numérico asociado (ej: 2)
    inf_final_valor = db.Column(db.Integer, nullable=True)
    # Columna 49: F.I.FINAL — fecha informe final
    f_i_final = db.Column(db.Date, nullable=True)
    # Columna 50: ESTADO7 (selector) — Valores: ESTADOS
    estado_inf_final = db.Column(db.String(15), nullable=True)

    # ── Columnas 51-53: Revisión-Entrega Final ────────────────────────────
    # Columna 51: R-E-FINAL (selector) — Valores: OPTS_SNC
    r_e_final = db.Column(db.String(15), nullable=True)
    # Columna 52: R-E-FINAL8 — valor numérico asociado (ej: 2.00)
    r_e_final_valor = db.Column(db.Numeric(5, 2), nullable=True)
    # Columna 53: F.R-E FINAL — fecha revisión-entrega final
    f_re_final = db.Column(db.Date, nullable=True)

    # ── Columnas 54-59: Constancia de Terminación ─────────────────────────
    # Columna 54: CONS.T (selector) — Valores: OPTS_SNC
    cons_t = db.Column(db.String(15), nullable=True)
    # Columna 55: C.T — valor numérico asociado (ej: 2.00)
    c_t_valor = db.Column(db.Numeric(5, 2), nullable=True)
    # Columna 56: F.C.T — fecha constancia de terminación
    f_ct = db.Column(db.Date, nullable=True)
    # Columna 57: DIA2
    f_ct_dia = db.Column(db.Integer, nullable=True)
    # Columna 58: MES2
    f_ct_mes = db.Column(db.String(15), nullable=True)
    # Columna 59: AÑO2
    f_ct_anio = db.Column(db.Integer, nullable=True)

    # ── Columnas 60-65: Cierre del Proceso ───────────────────────────────
    # Columna 60: PROMEDIO — Ej: "100%" (texto)
    promedio = db.Column(db.String(10), nullable=True)
    # Columna 61: TIEMPO DEL PROCESO — Ej: "3 meses 1 día"
    tiempo_proceso = db.Column(db.String(50), nullable=True)
    # Columna 62: RESUMEN -OBSERVACIONES — texto libre
    resumen_observaciones = db.Column(db.Text, nullable=True)
    # Columna 63: CARPETA — Ej: "BLOQUE 1"
    carpeta = db.Column(db.String(100), nullable=True)
    # Columna 64: PASO POR CONSTANCIA — Ej: "P.P.E.C-BLOQUE 1"
    paso_por_constancia = db.Column(db.String(100), nullable=True)
    # Columna 65: P.C. — Abreviatura de PASO POR CONSTANCIA
    pc = db.Column(db.String(50), nullable=True)

    # ── Campos de auditoría del sistema ───────────────────────────────────
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f'<Practica {self.no_constancia} — {self.nombre}>'

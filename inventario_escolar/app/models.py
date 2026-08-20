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

    @property
    def servicio_completado(self):
        """Retorna True si el alumno completó el Servicio Social (tiene al menos un documento Entregado o Recibido)."""
        exp_s = self.expedientes.filter_by(tipo_modulo='s', is_deleted=False).first()
        return exp_s and exp_s.documentos.filter(Documento.is_deleted == False, Documento.estado.in_(['Entregado', 'Recibido'])).first() is not None

    @property
    def practicas_completado(self):
        """Retorna True si el alumno completó las Prácticas Profesionales (tiene al menos un documento Entregado o Recibido)."""
        exp_p = self.expedientes.filter_by(tipo_modulo='p', is_deleted=False).first()
        return exp_p and exp_p.documentos.filter(Documento.is_deleted == False, Documento.estado.in_(['Entregado', 'Recibido'])).first() is not None

    @property
    def puede_realizar_estancia(self):
        """Retorna True si el alumno completó Servicio Social y Prácticas Profesionales."""
        return bool(self.servicio_completado and self.practicas_completado)

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


class Universidad(db.Model):
    __tablename__ = 'universidades'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    domicilio = db.Column(db.String(300), nullable=True)
    contacto = db.Column(db.String(150), nullable=True)
    telefono = db.Column(db.String(50), nullable=True)
    correo = db.Column(db.String(120), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Universidad {self.nombre}>'


class Expediente(db.Model):
    __tablename__ = 'expedientes'
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumnos.id'), nullable=False)
    tipo_modulo = db.Column(db.String(1), nullable=False)
    clave_expediente = db.Column(db.String(30), unique=True, nullable=False)
    sector = db.Column(db.String(30), nullable=True)  # Dependencias Servicio Social: Municipal / Estatal / Salud
    dependencia_id = db.Column(db.Integer, db.ForeignKey('dependencias.id'), nullable=True)
    universidad_id = db.Column(db.Integer, db.ForeignKey('universidades.id'), nullable=True)
    periodo = db.Column(db.String(100), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    documentos = db.relationship('Documento', backref='expediente', lazy='dynamic')
    universidad = db.relationship('Universidad', backref='expedientes')

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
    modulo_id    = db.Column(db.Integer, db.ForeignKey('modulos_vinculacion.id'), nullable=True)
    submodulo_id = db.Column(db.Integer, db.ForeignKey('submodulos_vinculacion.id'), nullable=True)
    nombre       = db.Column(db.String(200), nullable=False)
    descripcion  = db.Column(db.Text, nullable=True)
    ruta_archivo = db.Column(db.String(500), nullable=True)
    tipo_archivo = db.Column(db.String(50), nullable=True)   # pdf, docx, xlsx, …
    is_deleted   = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    modulo       = db.relationship('ModuloVinculacion', backref='archivos_raiz')

    def __repr__(self):
        return f'<ArchivoSubModulo {self.nombre}>'


# ── Módulo Compartidos ───────────────────────────────────────────────────────

class CarpetaCompartida(db.Model):
    __tablename__ = 'carpetas_compartidas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    icono = db.Column(db.String(50), default='fa-folder')
    color = db.Column(db.String(20), default='#4f46e5')
    
    archivos = db.relationship('ArchivoCompartido', backref='carpeta', lazy='dynamic', cascade='all, delete-orphan')
    creador = db.relationship('User', foreign_keys=[created_by_id])

    def __repr__(self):
        return f'<CarpetaCompartida {self.nombre}>'


class ArchivoCompartido(db.Model):
    __tablename__ = 'archivos_compartidos'
    id = db.Column(db.Integer, primary_key=True)
    carpeta_id = db.Column(db.Integer, db.ForeignKey('carpetas_compartidas.id'), nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    ruta_archivo = db.Column(db.String(500), nullable=True)
    tipo_archivo = db.Column(db.String(50), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    
    subidor = db.relationship('User', foreign_keys=[uploaded_by_id])

    def __repr__(self):
        return f'<ArchivoCompartido {self.nombre}>'

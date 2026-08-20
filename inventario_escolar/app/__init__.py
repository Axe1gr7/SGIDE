import os
from flask import Flask
from app.config import Config
from app.extensions import db, migrate, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # User loader para Flask-Login
    from app.models import User, ModuloVinculacion, CarpetaCompartida

    @app.context_processor
    def inject_global_vars():
        modulos = ModuloVinculacion.query.filter_by(is_deleted=False).order_by(ModuloVinculacion.orden).all()
        carpetas_compartidas = CarpetaCompartida.query.filter_by(is_deleted=False).order_by(CarpetaCompartida.nombre).all()
        return dict(modulos_vinculacion=modulos, carpetas_compartidas=carpetas_compartidas)

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        if user and not user.is_deleted:
            return user
        return None

    # Crear carpeta de uploads si no existe antes de registrar blueprints
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMPLATES_WORD_FOLDER'], exist_ok=True)

    # Registrar Blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.practicas import practicas_bp
    from app.blueprints.servicio import servicio_bp
    from app.blueprints.vinculacion import vinculacion_bp
    from app.blueprints.dependencias import dependencias_bp
    from app.blueprints.compartidos import compartidos_bp
    from app.blueprints.plantillas import plantillas_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(practicas_bp, url_prefix='/practicas')
    app.register_blueprint(servicio_bp, url_prefix='/servicio')
    app.register_blueprint(vinculacion_bp, url_prefix='/vinculacion')
    app.register_blueprint(dependencias_bp, url_prefix='/dependencias')
    app.register_blueprint(compartidos_bp, url_prefix='/compartidos')
    app.register_blueprint(plantillas_bp, url_prefix='/plantillas')

    return app

#!/bin/sh
set -e

echo 'Verificando estado de la Base de Datos...'
python -c "
import sys
from app import create_app
from app.extensions import db
import sqlalchemy as sa

app = create_app()
with app.app_context():
    try:
        if not sa.inspect(db.engine).has_table('users'):
            sys.exit(1)
        from app.models import User
        sys.exit(0 if User.query.first() else 1)
    except Exception:
        sys.exit(1)
" || NEED_SEED=1

echo 'Ejecutando verificacion idempotente de tablas y seeders...'
# seed-db crea/ajusta el esquema y retorna sin borrar datos si ya existe un usuario.
flask seed-db

echo 'Iniciando servidor...'
exec flask run --host=0.0.0.0 --port=5000
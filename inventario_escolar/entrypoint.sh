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

if [ "$NEED_SEED" = "1" ]; then
  echo 'Ejecutando creacion de tablas y seeders...'
  flask seed-db
else
  echo 'La base de datos ya tiene registros, omitiendo seeders.'
fi

echo 'Iniciando servidor...'
exec flask run --host=0.0.0.0 --port=5000
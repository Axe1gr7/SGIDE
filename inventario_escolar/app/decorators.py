from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def roles_required(*role_names):
    """Decorador para restringir acceso por rol."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role.nombre not in role_names:
                flash('No tienes permisos para acceder a esta sección.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def active_query(model):
    """Retorna query filtrando registros con soft delete."""
    return model.query.filter_by(is_deleted=False)

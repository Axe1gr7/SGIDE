import click
from app import create_app
from app.extensions import db
from app.models import Role, User, Carrera, Alumno, Expediente, Documento, Dependencia
from app.services.logic_expediente import registrar_alumno

app = create_app()


@app.cli.command('seed-db')
def seed_db():
    """Limpia todos los datos y puebla la base de datos con datos de ejemplo."""
    # --- 1. BORRAR TODOS LOS DATOS EXISTENTES ---
    # Borrar en orden inverso de dependencias (FK)
    click.echo('🗑️  Borrando todos los datos existentes...')
    db.session.query(Documento).delete()
    db.session.query(Expediente).delete()
    db.session.query(Alumno).delete()
    db.session.query(Dependencia).delete()
    db.session.query(User).delete()
    db.session.query(Carrera).delete()
    db.session.query(Role).delete()
    db.session.commit()
    click.echo('✅ Datos eliminados.')

    # --- 2. CREAR ROLES ---
    roles_data = ['Super Admin', 'Practicas', 'Servicio', 'Vinculacion']
    roles = {}
    for nombre in roles_data:
        rol = Role(nombre=nombre)
        db.session.add(rol)
        roles[nombre] = rol
    db.session.commit()
    click.echo('✅ Roles creados.')

    # --- 3. CREAR CARRERAS ---
    carreras_data = [
        (1, 'Programación'),
        (2, 'Biotecnología'),
        (3, 'PGA'),
        (4, 'Logística'),
        (5, 'Mecatrónica'),
    ]
    carreras = {}
    for prefijo, nombre in carreras_data:
        car = Carrera(nombre=nombre, prefijo_id=prefijo)
        db.session.add(car)
        carreras[nombre] = car
    db.session.commit()
    click.echo('✅ Carreras creadas.')

    # --- 4. CREAR DEPENDENCIAS DE EJEMPLO ---
    dependencias_data = [
        ('Hospital General Municipal', 'Servicio', 'Salud', 'Av. Salud #100', 'Dr. Gómez', '555-0101', 'hg@salud.gob.mx'),
        ('Ayuntamiento / Presidencia Municipal', 'Ambos', 'Municipal', 'Palacio Municipal', 'Lic. Torres', '555-0102', 'ayto@muni.gob.mx'),
        ('Gobierno del Estado - Dirección', 'Servicio', 'Estatal', 'Centro Estatal', 'Mtra. Ruiz', '555-0103', 'dir@estado.gob.mx'),
        ('Clínica de Especialidades', 'Servicio', 'Salud', 'Zona Médica', 'Dr. Castro', '555-0104', 'clinica@salud.gob.mx'),
        ('Empresa Tecnológica SA', 'Practicas', None, 'Parque Industrial', 'Ing. Rivero', '555-0105', 'contacto@empresa.mx'),
    ]
    dependencias = []
    for (nombre, tipo, sector, domicilio, contacto, telefono, correo) in dependencias_data:
        dep = Dependencia(nombre=nombre, tipo=tipo, sector=sector, domicilio=domicilio,
                          contacto=contacto, telefono=telefono, correo=correo)
        db.session.add(dep)
        dependencias.append(dep)
    db.session.commit()
    click.echo('✅ Dependencias de ejemplo creadas.')

    # --- 5. CREAR USUARIOS DE EJEMPLO (uno por cada rol) ---
    usuarios_data = [
        ('admin', 'Administrador General', 'Super Admin'),
        ('practicas', 'Coordinador de Prácticas', 'Practicas'),
        ('servicio', 'Coordinador de Servicio Social', 'Servicio'),
        ('vinculacion', 'Coordinador de Vinculación', 'Vinculacion'),
    ]
    for (username, nombre_completo, rol_nombre) in usuarios_data:
        user = User(username=username, nombre_completo=nombre_completo, role_id=roles[rol_nombre].id)
        user.set_password('cambiar_123')
        db.session.add(user)
    db.session.commit()
    click.echo('✅ Usuarios de ejemplo creados.')

    # --- 6. CREAR ALUMNOS DE EJEMPLO (con expedientes automáticos) ---
    alumnos_data = [
        ('Juan Pérez López', '20210001', 18, 21, 'Activo', 'Programación'),
        ('María García Ruiz', '20210002', 18, 21, 'Egresado', 'Biotecnología'),
        ('Carlos Hernández Díaz', '20210003', 20, 23, 'Activo', 'PGA'),
        ('Ana Martínez Cruz', '20210004', 20, None, 'Activo', 'Logística'),
        ('Luis Rodríguez Mora', '20210005', 22, None, 'Inactivo', 'Mecatrónica'),
        ('Sofía Flores Vega', '20210006', 18, 21, 'Egresado', 'Programación'),
    ]
    for (nombre, matricula, anio_ini, anio_fin, estatus, carrera_nombre) in alumnos_data:
        car = carreras[carrera_nombre]
        try:
            registrar_alumno(nombre, matricula, anio_ini, car.id, car.prefijo_id,
                             anio_egreso=anio_fin, estatus=estatus)
        except Exception as e:
            click.echo(f'⚠️  Error al registrar a {nombre}: {e}')
    db.session.commit()
    click.echo('✅ Alumnos de ejemplo con expedientes creados.')

    # --- 7. ASIGNAR DEPENDENCIA Y SECTOR A EXPEDIENTES DE SERVICIO ---
    deps_servicio = [d for d in dependencias if d.tipo in ('Servicio', 'Ambos')]
    if deps_servicio:
        exps_servicio = Expediente.query.filter_by(tipo_modulo='s').all()
        for i, exp in enumerate(exps_servicio):
            dep = deps_servicio[i % len(deps_servicio)]
            exp.dependencia_id = dep.id
            if dep.sector:
                exp.sector = dep.sector
        db.session.commit()
        click.echo('✅ Dependencias y sector asignados a expedientes de servicio.')

    click.echo('🎉 Base de datos poblada exitosamente con datos de ejemplo.')
    click.echo('')
    click.echo('Usuarios de ejemplo (contraseña para todos: cambiar_123):')
    for (username, nombre, _) in usuarios_data:
        click.echo(f'  - {username} / cambiar_123  ({nombre})')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


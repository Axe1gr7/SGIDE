# TODO - Mejoras SGIDE

## Anotaciones a implementar (completadas)
1. ✅ Columna de estatus de expedientes/alumnos (Activo, Inactivo, Egresado)
2. ✅ Generación completa de alumnos (ej: 2018-2021)
3. ✅ Sector (Municipal, Estatal, Salud) para dependencias de Servicio Social
4. ✅ Vinculación: visualizar estatus de los alumnos
5. ✅ Carpetas por apartados con subcarpetas por años

## Resumen de cambios realizados/verificados

### Modelo de datos (`app/models.py`)
- `Alumno`: +`anio_egreso`, +`estatus` (Activo/Inactivo/Egresado), campos nombre/matrícula/carrera/expediente_base ahora `nullable`
- `Alumno.generacion_completa`: propiedad que devuelve '2018-2021'
- `Dependencia`: nuevo modelo (nombre, tipo, sector, domicilio, contacto, telefono, correo)
- `Expediente`: +`sector`, +`dependencia_id` FK a dependencias

### Migraciones
- `081591864ffd`: estatus, anio_egreso, sector
- `a1b2c3d4e5f6`: tabla dependencias + FK dependencia_id

### Blueprints
- `admin`: crear/editar alumno aceptan valores opcionales
- `servicio`: +filtro sector, +asignar dependencia, +actualizar sector
- `practicas`: +asignar dependencia
- `vinculacion`: muestra estatus (via lista.html)
- `dependencias`: CRUD + importación Excel (nuevo)
- `plantillas`: gestión de machotes Word (nuevo)
- `dashboard`, `run`: consistentes con seed

### Templates
- `alumno_form.html`: campos opcionales
- `alumnos.html`: +columna Estatus, +generación completa, manejo de None
- `lista.html`: +columna Generación, +Estatus, +Sector (servicio)
- `detalle.html`: +Estatus, +dependencia/sector
- `dependencias/*`: catálogo CRUD/import (nuevos)
- `plantillas/lista.html`: gestión machotes (nuevo)

### Servicios
- `logic_expediente`: registrar_alumno acepta None y genera clave temporal `TMP-`
- `logic_excel`: mapeo flexible de columnas (español/inglés), admite datos faltantes
- `logic_word`: maneja None, +estatus, +sector, +dependencia en contexto
- `file_manager`: rutas por apartado/año/carrera/alumno

### CSS
- Badges para Activo, Inactivo, Egresado, Municipal, Estatal, Salud

## Verificación
- ✅ Todos los archivos Python compilan (py_compile) correctamente
- ✅ App se inicializa correctamente (50 URLs registradas)
- ✅ Migraciones aplicadas a la BD (head = a1b2c3d4e5f6) usando `DATABASE_URL` con localhost
- ✅ Corregido `generate_templates.py` (ruta incorrecta → ruta relativa del proyecto)
- ✅ Nota: al correr localmente usar `DATABASE_URL` con localhost (el `.env` usa `db` que es el hostname de Docker)
- ✅ Compilación final de todos los módulos OK (compileall)
- ✅ App carga con 50 URLs (dependencias + plantillas registrados)
- ⏳ Poblar/verificar datos: `flask seed-db` y/o importar datos reales (opcional)


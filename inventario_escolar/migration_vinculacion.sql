-- =========================================================
-- Migración: Tablas del sistema de Módulos de Vinculación
-- Fecha: 2026-08-14
-- Ejecutar: docker compose exec db psql -U sgide_user -d inventario_escolar -f /dev/stdin < migration_vinculacion.sql
-- =========================================================

-- Tabla principal de módulos
CREATE TABLE IF NOT EXISTS modulos_vinculacion (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(200) NOT NULL,
    descripcion TEXT,
    icono       VARCHAR(80)  DEFAULT 'fa-folder',
    color       VARCHAR(30)  DEFAULT '#4f46e5',
    orden       INTEGER      DEFAULT 0,
    is_deleted  BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Tabla de sub-módulos
CREATE TABLE IF NOT EXISTS submodulos_vinculacion (
    id          SERIAL PRIMARY KEY,
    modulo_id   INTEGER NOT NULL REFERENCES modulos_vinculacion(id) ON DELETE CASCADE,
    nombre      VARCHAR(200) NOT NULL,
    descripcion TEXT,
    icono       VARCHAR(80)  DEFAULT 'fa-folder-open',
    orden       INTEGER      DEFAULT 0,
    is_deleted  BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Tabla de archivos dentro de sub-módulos
CREATE TABLE IF NOT EXISTS archivos_submodulo (
    id           SERIAL PRIMARY KEY,
    submodulo_id INTEGER NOT NULL REFERENCES submodulos_vinculacion(id) ON DELETE CASCADE,
    nombre       VARCHAR(200) NOT NULL,
    descripcion  TEXT,
    ruta_archivo VARCHAR(500),
    tipo_archivo VARCHAR(50),
    is_deleted   BOOLEAN      DEFAULT FALSE,
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Indices útiles
CREATE INDEX IF NOT EXISTS ix_modulos_vinculacion_is_deleted     ON modulos_vinculacion(is_deleted);
CREATE INDEX IF NOT EXISTS ix_submodulos_vinculacion_modulo_id   ON submodulos_vinculacion(modulo_id);
CREATE INDEX IF NOT EXISTS ix_submodulos_vinculacion_is_deleted  ON submodulos_vinculacion(is_deleted);
CREATE INDEX IF NOT EXISTS ix_archivos_submodulo_submodulo_id    ON archivos_submodulo(submodulo_id);
CREATE INDEX IF NOT EXISTS ix_archivos_submodulo_is_deleted      ON archivos_submodulo(is_deleted);

-- Insertar en alembic_version para que flask-migrate no cree la migración de nuevo
-- (Opcional: comenta esta línea si prefieres usar flask db stamp head después)
-- INSERT INTO alembic_version (version_num) VALUES ('vinculacion_modules_001') ON CONFLICT DO NOTHING;

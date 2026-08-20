-- =========================================================
-- Migracion: Tabla del modulo de Practicas Profesionales
-- Fecha: 2026-08-19
-- Origen: PRACTICAS_1.xlsx (65 columnas mapeadas exactamente)
-- Ejecutar:
--   docker compose exec db psql -U sgide_user -d inventario_escolar -f /dev/stdin < migration_practicas.sql
-- =========================================================

CREATE TABLE IF NOT EXISTS practicas (

    -- Clave primaria del sistema
    id                   SERIAL PRIMARY KEY,

    -- Columna 1: No. REGISTRO
    no_registro          INTEGER,

    -- Columna 2: CONSECUTIVO
    consecutivo          INTEGER,

    -- Columna 3: No. CONSTANCIA  Ej: PC06/MATUTINO/002/2026
    no_constancia        VARCHAR(50),

    -- Columna 4: NOMBRE
    nombre               VARCHAR(250),

    -- Columna 5: Nombre Minusculas
    nombre_minusculas    VARCHAR(250),

    -- Columna 6: MATRICULA
    matricula            VARCHAR(50),

    -- Columna 7: TELEFONO
    telefono             VARCHAR(20),

    -- Columna 8: CORREO ESTUDIANTE
    correo_estudiante    VARCHAR(150),

    -- Columna 9: GRADO-CARRERA (selector)
    -- Valores: 5T0-MECA-AMBI, 5T0-MECA-BM, ..., 6T0-PGA-AV
    grado_carrera        VARCHAR(30),

    -- Columna 10: TURNO (selector) — MATUTINO / VESPERTINO
    turno                VARCHAR(15),

    -- Columna 11: CARRERA (selector)
    -- Valores: MECATRONICA, BIOTECNOLOGIA, LOGISTICA, PROGRAMACION
    carrera              VARCHAR(50),

    -- Columna 12: OBSERVACIONES (selector) — CONCLUIDO / EN TRAMITE
    observaciones        VARCHAR(20),

    -- Columna 13: PROCESO (selector)
    -- Valores: EMPRESA, INSTITUCION, PROYECTO, DUAL, CERTIFICACION
    proceso              VARCHAR(30),

    -- Columna 14: EMPRESA
    empresa              VARCHAR(250),

    -- Columna 15: SECTOR (selector)
    -- Valores: SECTOR PUBLICO, MICROEMPRESAS, PEQUENAS EMPRESAS,
    --          MEDIANAS EMPRESAS, GRANDES EMPRESAS,
    --          SECTOR SOCIAL, ORGANIZACIONES DE LA SOCIEDAD CIVIL
    sector               VARCHAR(60),

    -- Columna 16: NOMBRE DEL PROYECTO
    nombre_proyecto      VARCHAR(300),

    -- Columna 17: TEL. EMPRESA
    tel_empresa          VARCHAR(20),

    -- Columna 18: DIRECCION EMPRESA
    direccion_empresa    VARCHAR(400),

    -- Columna 19: CORR. EM
    correo_empresa       VARCHAR(150),

    -- Columna 20: GENERACION  Ej: "23-26"
    generacion           VARCHAR(10),

    -- Columna 21: H/M (selector) — HOMBRE / MUJER
    sexo                 VARCHAR(10),

    -- Columna 22: BECADOS  Ej: 1.00
    becados              NUMERIC(10, 2),

    -- Columna 23: MONTO  Puede ser numerico o "N/A"
    monto                VARCHAR(20),

    -- Columnas 24-29: Solicitud de Practicas
    -- Columna 24: S. PRAC (selector) — SI / NO / CORREGIR
    s_prac               VARCHAR(15),
    -- Columna 25: S. PRAC. — fecha serializada raw del Excel
    s_prac_fecha_excel   DATE,
    -- Columna 26: F. INICIO — fecha de inicio de practicas
    f_inicio             DATE,
    -- Columna 27: DIA
    f_inicio_dia         INTEGER,
    -- Columna 28: MES
    f_inicio_mes         VARCHAR(15),
    -- Columna 29: ANO
    f_inicio_anio        INTEGER,

    -- Columnas 30-32: Carta de Presentacion
    -- Columna 30: C.PRES. (selector) — SI / NO / CORREGIR
    c_pres               VARCHAR(15),
    -- Columna 31: C.PRES.2 — fecha serializada raw del Excel
    c_pres_fecha_excel   DATE,
    -- Columna 32: F.C.P — fecha carta de presentacion
    f_cp                 DATE,

    -- Columnas 33-38: Carta de Aceptacion
    -- Columna 33: C. ACEP (selector) — SI / NO / CORREGIR
    c_acep               VARCHAR(15),
    -- Columna 34: C. ACEP. — fecha serializada raw del Excel
    c_acep_fecha_excel   DATE,
    -- Columna 35: F.C.A — fecha carta de aceptacion
    f_ca                 DATE,
    -- Columna 36: DIA 3
    f_ca_dia             INTEGER,
    -- Columna 37: MES4
    f_ca_mes             VARCHAR(15),
    -- Columna 38: ANO 5
    f_ca_anio            INTEGER,

    -- Columnas 39-41: Plan de Trabajo
    -- Columna 39: P. TRABJ (selector) — SI / NO / CORREGIR
    p_trabj              VARCHAR(15),
    -- Columna 40: P. TRABJ. — fecha serializada raw del Excel
    p_trabj_fecha_excel  DATE,
    -- Columna 41: F. P.TR — fecha plan de trabajo
    f_ptr                DATE,

    -- Columnas 42-46: Informe Intermedio
    -- Columna 42: I. INTER (selector) — SI / NO / CORREGIR
    i_inter              VARCHAR(15),
    -- Columna 43: I. INTER. — fecha serializada raw del Excel
    i_inter_fecha_excel  DATE,
    -- Columna 44: F.I.I. — fecha informe intermedio
    f_ii                 DATE,
    -- Columna 45: F.L. I.I. — fecha limite informe intermedio
    f_l_ii               DATE,
    -- Columna 46: ESTADO (selector) — ENTREGADO / ATRASADO
    estado               VARCHAR(15),

    -- Columnas 47-50: Informe Final
    -- Columna 47: INF. FINAL (selector) — SI / NO / CORREGIR
    inf_final            VARCHAR(15),
    -- Columna 48: INF. FINAL6 — valor numerico asociado (ej: 2)
    inf_final_valor      INTEGER,
    -- Columna 49: F.I.FINAL — fecha informe final
    f_i_final            DATE,
    -- Columna 50: ESTADO7 (selector) — ENTREGADO / ATRASADO
    estado_inf_final     VARCHAR(15),

    -- Columnas 51-53: Revision-Entrega Final
    -- Columna 51: R-E-FINAL (selector) — SI / NO / CORREGIR
    r_e_final            VARCHAR(15),
    -- Columna 52: R-E-FINAL8 — valor numerico asociado (ej: 2.00)
    r_e_final_valor      NUMERIC(5, 2),
    -- Columna 53: F.R-E FINAL — fecha revision-entrega final
    f_re_final           DATE,

    -- Columnas 54-59: Constancia de Terminacion
    -- Columna 54: CONS.T (selector) — SI / NO / CORREGIR
    cons_t               VARCHAR(15),
    -- Columna 55: C.T — valor numerico asociado (ej: 2.00)
    c_t_valor            NUMERIC(5, 2),
    -- Columna 56: F.C.T — fecha constancia de terminacion
    f_ct                 DATE,
    -- Columna 57: DIA2
    f_ct_dia             INTEGER,
    -- Columna 58: MES2
    f_ct_mes             VARCHAR(15),
    -- Columna 59: ANO2
    f_ct_anio            INTEGER,

    -- Columnas 60-65: Cierre del Proceso
    -- Columna 60: PROMEDIO  Ej: "100%"
    promedio             VARCHAR(10),
    -- Columna 61: TIEMPO DEL PROCESO  Ej: "3 meses 1 dia"
    tiempo_proceso       VARCHAR(50),
    -- Columna 62: RESUMEN -OBSERVACIONES — texto libre
    resumen_observaciones TEXT,
    -- Columna 63: CARPETA  Ej: "BLOQUE 1"
    carpeta              VARCHAR(100),
    -- Columna 64: PASO POR CONSTANCIA  Ej: "P.P.E.C-BLOQUE 1"
    paso_por_constancia  VARCHAR(100),
    -- Columna 65: P.C. — Abreviatura de PASO POR CONSTANCIA
    pc                   VARCHAR(50),

    -- Campos de auditoria del sistema
    is_deleted           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at           TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Comentarios sobre cada columna (encabezado original del Excel)
COMMENT ON TABLE  practicas                       IS 'Modulo de Practicas Profesionales — mapeado desde PRACTICAS_1.xlsx';
COMMENT ON COLUMN practicas.no_registro           IS 'No. REGISTRO';
COMMENT ON COLUMN practicas.consecutivo           IS 'CONSECUTIVO';
COMMENT ON COLUMN practicas.no_constancia         IS 'No. CONSTANCIA';
COMMENT ON COLUMN practicas.nombre                IS 'NOMBRE';
COMMENT ON COLUMN practicas.nombre_minusculas     IS 'Nombre Minusculas';
COMMENT ON COLUMN practicas.matricula             IS 'MATRICULA';
COMMENT ON COLUMN practicas.telefono              IS 'TELEFONO';
COMMENT ON COLUMN practicas.correo_estudiante     IS 'CORREO ESTUDIANTE';
COMMENT ON COLUMN practicas.grado_carrera         IS 'GRADO-CARRERA';
COMMENT ON COLUMN practicas.turno                 IS 'TURNO';
COMMENT ON COLUMN practicas.carrera               IS 'CARRERA';
COMMENT ON COLUMN practicas.observaciones         IS 'OBSERVACIONES';
COMMENT ON COLUMN practicas.proceso               IS 'PROCESO';
COMMENT ON COLUMN practicas.empresa               IS 'EMPRESA';
COMMENT ON COLUMN practicas.sector                IS 'SECTOR';
COMMENT ON COLUMN practicas.nombre_proyecto       IS 'NOMBRE DEL PROYECTO';
COMMENT ON COLUMN practicas.tel_empresa           IS 'TEL. EMPRESA';
COMMENT ON COLUMN practicas.direccion_empresa     IS 'DIRECCION EMPRESA';
COMMENT ON COLUMN practicas.correo_empresa        IS 'CORR. EM';
COMMENT ON COLUMN practicas.generacion            IS 'GENERACION';
COMMENT ON COLUMN practicas.sexo                  IS 'H/M';
COMMENT ON COLUMN practicas.becados               IS 'BECADOS';
COMMENT ON COLUMN practicas.monto                 IS 'MONTO';
COMMENT ON COLUMN practicas.s_prac                IS 'S. PRAC';
COMMENT ON COLUMN practicas.s_prac_fecha_excel    IS 'S. PRAC.';
COMMENT ON COLUMN practicas.f_inicio              IS 'F. INICIO';
COMMENT ON COLUMN practicas.f_inicio_dia          IS 'DIA';
COMMENT ON COLUMN practicas.f_inicio_mes          IS 'MES';
COMMENT ON COLUMN practicas.f_inicio_anio         IS 'ANO';
COMMENT ON COLUMN practicas.c_pres                IS 'C.PRES.';
COMMENT ON COLUMN practicas.c_pres_fecha_excel    IS 'C.PRES.2';
COMMENT ON COLUMN practicas.f_cp                  IS 'F.C.P';
COMMENT ON COLUMN practicas.c_acep                IS 'C. ACEP';
COMMENT ON COLUMN practicas.c_acep_fecha_excel    IS 'C. ACEP.';
COMMENT ON COLUMN practicas.f_ca                  IS 'F.C.A';
COMMENT ON COLUMN practicas.f_ca_dia              IS 'DIA 3';
COMMENT ON COLUMN practicas.f_ca_mes              IS 'MES4';
COMMENT ON COLUMN practicas.f_ca_anio             IS 'ANO 5';
COMMENT ON COLUMN practicas.p_trabj               IS 'P. TRABJ';
COMMENT ON COLUMN practicas.p_trabj_fecha_excel   IS 'P. TRABJ.';
COMMENT ON COLUMN practicas.f_ptr                 IS 'F. P.TR';
COMMENT ON COLUMN practicas.i_inter               IS 'I. INTER';
COMMENT ON COLUMN practicas.i_inter_fecha_excel   IS 'I. INTER.';
COMMENT ON COLUMN practicas.f_ii                  IS 'F.I.I.';
COMMENT ON COLUMN practicas.f_l_ii                IS 'F.L. I.I.';
COMMENT ON COLUMN practicas.estado                IS 'ESTADO';
COMMENT ON COLUMN practicas.inf_final             IS 'INF. FINAL';
COMMENT ON COLUMN practicas.inf_final_valor       IS 'INF. FINAL6';
COMMENT ON COLUMN practicas.f_i_final             IS 'F.I.FINAL';
COMMENT ON COLUMN practicas.estado_inf_final      IS 'ESTADO7';
COMMENT ON COLUMN practicas.r_e_final             IS 'R-E-FINAL';
COMMENT ON COLUMN practicas.r_e_final_valor       IS 'R-E-FINAL8';
COMMENT ON COLUMN practicas.f_re_final            IS 'F.R-E FINAL';
COMMENT ON COLUMN practicas.cons_t                IS 'CONS.T';
COMMENT ON COLUMN practicas.c_t_valor             IS 'C.T';
COMMENT ON COLUMN practicas.f_ct                  IS 'F.C.T';
COMMENT ON COLUMN practicas.f_ct_dia              IS 'DIA2';
COMMENT ON COLUMN practicas.f_ct_mes              IS 'MES2';
COMMENT ON COLUMN practicas.f_ct_anio             IS 'ANO2';
COMMENT ON COLUMN practicas.promedio              IS 'PROMEDIO';
COMMENT ON COLUMN practicas.tiempo_proceso        IS 'TIEMPO DEL PROCESO';
COMMENT ON COLUMN practicas.resumen_observaciones IS 'RESUMEN -OBSERVACIONES';
COMMENT ON COLUMN practicas.carpeta               IS 'CARPETA';
COMMENT ON COLUMN practicas.paso_por_constancia   IS 'PASO POR CONSTANCIA';
COMMENT ON COLUMN practicas.pc                    IS 'P.C.';

-- Indices
CREATE INDEX IF NOT EXISTS ix_practicas_matricula    ON practicas(matricula);
CREATE INDEX IF NOT EXISTS ix_practicas_no_registro  ON practicas(no_registro);
CREATE INDEX IF NOT EXISTS ix_practicas_is_deleted   ON practicas(is_deleted);
CREATE INDEX IF NOT EXISTS ix_practicas_carrera      ON practicas(carrera);
CREATE INDEX IF NOT EXISTS ix_practicas_turno        ON practicas(turno);
CREATE INDEX IF NOT EXISTS ix_practicas_proceso      ON practicas(proceso);

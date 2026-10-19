-- =============================================================
-- PreVet · Script de base de datos (tablas, índices, grupos y catálogos)
-- Proyecto APT Capstone PTY4614 · Duoc UC · Katalina Mora y Uciell Madrid
-- Generado el 19-10-2026 a partir de las migraciones de Django (sistema/)
-- Motor: SQLite (desarrollo). En producción el mismo modelo corre sobre PostgreSQL.
-- No incluye usuarios ni contraseñas: las cuentas se crean con
--   python manage.py createsuperuser  y desde el menú Personal del sistema.
-- =============================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- -------------------------------------------------------------
-- 1. TABLAS
-- -------------------------------------------------------------

-- Tabla django_content_type
CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

-- Tabla auth_permission
CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

-- Tabla auth_group
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

-- Tabla auth_group_permissions
CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla auth_user
CREATE TABLE "auth_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "last_name" varchar(150) NOT NULL, "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "first_name" varchar(150) NOT NULL);

-- Tabla auth_user_groups
CREATE TABLE "auth_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla auth_user_user_permissions
CREATE TABLE "auth_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla usuarios_perfil
CREATE TABLE "usuarios_perfil" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "rol" varchar(20) NOT NULL, "es_administrador" bool NOT NULL, "telefono" varchar(20) NOT NULL, "direccion" varchar(200) NOT NULL, "usuario_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla mascotas_especie
CREATE TABLE "mascotas_especie" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(50) NOT NULL UNIQUE);

-- Tabla mascotas_raza
CREATE TABLE "mascotas_raza" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "especie_id" bigint NOT NULL REFERENCES "mascotas_especie" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla mascotas_cliente
CREATE TABLE "mascotas_cliente" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "rut" varchar(12) NOT NULL UNIQUE, "nombres" varchar(80) NOT NULL, "apellidos" varchar(80) NOT NULL, "telefono" varchar(20) NOT NULL, "email" varchar(254) NOT NULL, "direccion" varchar(200) NOT NULL, "activo" bool NOT NULL, "fecha_registro" datetime NOT NULL, "canal_preferido" varchar(10) DEFAULT 'whatsapp' NOT NULL, "comuna" varchar(60) DEFAULT '' NOT NULL, "consentimiento_datos" bool DEFAULT 0 NOT NULL, "contacto_emergencia" varchar(120) DEFAULT '' NOT NULL, "fecha_consentimiento" datetime NULL, "region" varchar(60) DEFAULT '' NOT NULL, "telefono_emergencia" varchar(20) DEFAULT '' NOT NULL, "usuario_id" integer NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla mascotas_mascota
CREATE TABLE "mascotas_mascota" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "sexo" varchar(10) NOT NULL, "fecha_nacimiento" date NULL, "activo" bool NOT NULL, "fecha_registro" datetime NOT NULL, "especie_id" bigint NOT NULL REFERENCES "mascotas_especie" ("id") DEFERRABLE INITIALLY DEFERRED, "raza_id" bigint NULL REFERENCES "mascotas_raza" ("id") DEFERRABLE INITIALLY DEFERRED, "foto_version" integer unsigned DEFAULT 0 NOT NULL CHECK ("foto_version" >= 0), "alergias" text DEFAULT '' NOT NULL, "color" varchar(80) DEFAULT '' NOT NULL, "condiciones" text DEFAULT '' NOT NULL, "esterilizada" bool NULL, "microchip" varchar(15) DEFAULT '' NOT NULL, "observaciones" text DEFAULT '' NOT NULL, "peso_kg" decimal NULL, "tiene_microchip" bool NULL);

-- Tabla mascotas_tenencia
CREATE TABLE "mascotas_tenencia" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "relacion" varchar(20) NOT NULL, "es_principal" bool NOT NULL, "desde" date NOT NULL, "cliente_id" bigint NOT NULL REFERENCES "mascotas_cliente" ("id") DEFERRABLE INITIALLY DEFERRED, "mascota_id" bigint NOT NULL REFERENCES "mascotas_mascota" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "un_vinculo_por_cliente_y_mascota" UNIQUE ("cliente_id", "mascota_id"));

-- Tabla mascotas_fotomascota
CREATE TABLE "mascotas_fotomascota" ("mascota_id" bigint NOT NULL PRIMARY KEY REFERENCES "mascotas_mascota" ("id") DEFERRABLE INITIALLY DEFERRED, "imagen" BLOB NOT NULL, "tipo" varchar(30) NOT NULL, "actualizada" datetime NOT NULL, "subida_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla citas_tipoatencion
CREATE TABLE "citas_tipoatencion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "duracion_minutos" integer NOT NULL, "precio" integer NOT NULL, "activo" bool NOT NULL);

-- Tabla citas_horarioatencion
CREATE TABLE "citas_horarioatencion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "dia_semana" integer NOT NULL, "hora_inicio" time NOT NULL, "hora_fin" time NOT NULL, "activo" bool NOT NULL, "veterinario_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla citas_cita
CREATE TABLE "citas_cita" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "fecha" date NOT NULL, "hora" time NOT NULL, "estado" varchar(20) NOT NULL, "notas" text NOT NULL, "fecha_creacion" datetime NOT NULL, "fecha_cancelacion" datetime NULL, "fecha_marcada_no_asistio" datetime NULL, "cancelada_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "mascota_id" bigint NOT NULL REFERENCES "mascotas_mascota" ("id") DEFERRABLE INITIALLY DEFERRED, "veterinario_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tipo_atencion_id" bigint NOT NULL REFERENCES "citas_tipoatencion" ("id") DEFERRABLE INITIALLY DEFERRED, "cliente_id" bigint NOT NULL REFERENCES "mascotas_cliente" ("id") DEFERRABLE INITIALLY DEFERRED, "hora_llegada" datetime NULL, "motivo_cancelacion" varchar(200) NOT NULL);

-- -------------------------------------------------------------
-- 2. ÍNDICES
-- -------------------------------------------------------------
CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id");
CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id");
CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id");
CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id");
CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename");
CREATE INDEX "auth_user_groups_group_id_97559544" ON "auth_user_groups" ("group_id");
CREATE INDEX "auth_user_groups_user_id_6a12ed8b" ON "auth_user_groups" ("user_id");
CREATE UNIQUE INDEX "auth_user_groups_user_id_group_id_94350c0c_uniq" ON "auth_user_groups" ("user_id", "group_id");
CREATE INDEX "auth_user_user_permissions_permission_id_1fbb5f2c" ON "auth_user_user_permissions" ("permission_id");
CREATE INDEX "auth_user_user_permissions_user_id_a95ead1b" ON "auth_user_user_permissions" ("user_id");
CREATE UNIQUE INDEX "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq" ON "auth_user_user_permissions" ("user_id", "permission_id");
CREATE INDEX "citas_cita_cancelada_por_id_2fdf4563" ON "citas_cita" ("cancelada_por_id");
CREATE INDEX "citas_cita_cliente_id_c277d0e3" ON "citas_cita" ("cliente_id");
CREATE INDEX "citas_cita_mascota_id_57d42afa" ON "citas_cita" ("mascota_id");
CREATE INDEX "citas_cita_tipo_atencion_id_0a46633e" ON "citas_cita" ("tipo_atencion_id");
CREATE INDEX "citas_cita_veterinario_id_7789b1f4" ON "citas_cita" ("veterinario_id");
CREATE UNIQUE INDEX "una_cita_activa_por_bloque" ON "citas_cita" ("veterinario_id", "fecha", "hora") WHERE NOT ("estado" = 'cancelada');
CREATE INDEX "citas_horarioatencion_veterinario_id_a96ae994" ON "citas_horarioatencion" ("veterinario_id");
CREATE UNIQUE INDEX "citas_horarioatencion_veterinario_id_dia_semana_hora_inicio_9b2cedbf_uniq" ON "citas_horarioatencion" ("veterinario_id", "dia_semana", "hora_inicio");
CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model");
CREATE INDEX "mascotas_fotomascota_subida_por_id_bab89009" ON "mascotas_fotomascota" ("subida_por_id");
CREATE INDEX "mascotas_mascota_especie_id_d94c2cdc" ON "mascotas_mascota" ("especie_id");
CREATE INDEX "mascotas_mascota_raza_id_076f2c9b" ON "mascotas_mascota" ("raza_id");
CREATE UNIQUE INDEX "microchip_unico" ON "mascotas_mascota" ("microchip") WHERE NOT ("microchip" = '');
CREATE INDEX "mascotas_raza_especie_id_e3a016eb" ON "mascotas_raza" ("especie_id");
CREATE UNIQUE INDEX "mascotas_raza_especie_id_nombre_aeb5ae75_uniq" ON "mascotas_raza" ("especie_id", "nombre");
CREATE INDEX "mascotas_tenencia_cliente_id_7adc502f" ON "mascotas_tenencia" ("cliente_id");
CREATE INDEX "mascotas_tenencia_mascota_id_a038bafb" ON "mascotas_tenencia" ("mascota_id");
CREATE UNIQUE INDEX "un_responsable_principal_por_mascota" ON "mascotas_tenencia" ("mascota_id") WHERE "es_principal";

-- -------------------------------------------------------------
-- 3. TIPOS DE CONTENIDO Y PERMISOS (los crea Django)
-- -------------------------------------------------------------
INSERT INTO "django_content_type" (id, app_label, model) VALUES (1, 'admin', 'logentry');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (2, 'auth', 'permission');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (3, 'auth', 'group');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (4, 'auth', 'user');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (5, 'citas', 'tipoatencion');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (6, 'citas', 'horarioatencion');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (7, 'citas', 'cita');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (8, 'contenttypes', 'contenttype');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (9, 'mascotas', 'especie');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (10, 'mascotas', 'raza');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (11, 'mascotas', 'mascota');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (12, 'mascotas', 'cliente');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (13, 'mascotas', 'tenencia');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (14, 'mascotas', 'fotomascota');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (15, 'sessions', 'session');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (16, 'usuarios', 'perfil');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (17, 'usuarios', 'grupopermisos');
INSERT INTO "django_content_type" (id, app_label, model) VALUES (18, 'usuarios', 'personal');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (1, 1, 'add_logentry', 'Can add log entry');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (2, 1, 'change_logentry', 'Can change log entry');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (3, 1, 'delete_logentry', 'Can delete log entry');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (4, 1, 'view_logentry', 'Can view log entry');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (5, 2, 'add_permission', 'Can add permission');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (6, 2, 'change_permission', 'Can change permission');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (7, 2, 'delete_permission', 'Can delete permission');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (8, 2, 'view_permission', 'Can view permission');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (9, 3, 'add_group', 'Can add group');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (10, 3, 'change_group', 'Can change group');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (11, 3, 'delete_group', 'Can delete group');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (12, 3, 'view_group', 'Can view group');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (13, 4, 'add_user', 'Can add user');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (14, 4, 'change_user', 'Can change user');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (15, 4, 'delete_user', 'Can delete user');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (16, 4, 'view_user', 'Can view user');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (17, 5, 'add_tipoatencion', 'Can add Tipo de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (18, 5, 'change_tipoatencion', 'Can change Tipo de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (19, 5, 'delete_tipoatencion', 'Can delete Tipo de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (20, 5, 'view_tipoatencion', 'Can view Tipo de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (21, 6, 'add_horarioatencion', 'Can add Horario de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (22, 6, 'change_horarioatencion', 'Can change Horario de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (23, 6, 'delete_horarioatencion', 'Can delete Horario de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (24, 6, 'view_horarioatencion', 'Can view Horario de atención');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (25, 7, 'add_cita', 'Can add Cita');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (26, 7, 'change_cita', 'Can change Cita');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (27, 7, 'delete_cita', 'Can delete Cita');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (28, 7, 'view_cita', 'Can view Cita');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (29, 7, 'ver_riesgo', 'Ver las horas en riesgo');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (30, 7, 'ver_indicadores', 'Ver los indicadores');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (31, 8, 'add_contenttype', 'Can add content type');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (32, 8, 'change_contenttype', 'Can change content type');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (33, 8, 'delete_contenttype', 'Can delete content type');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (34, 8, 'view_contenttype', 'Can view content type');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (35, 9, 'add_especie', 'Can add tipo de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (36, 9, 'change_especie', 'Can change tipo de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (37, 9, 'delete_especie', 'Can delete tipo de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (38, 9, 'view_especie', 'Can view tipo de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (39, 10, 'add_raza', 'Can add raza');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (40, 10, 'change_raza', 'Can change raza');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (41, 10, 'delete_raza', 'Can delete raza');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (42, 10, 'view_raza', 'Can view raza');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (43, 11, 'add_mascota', 'Can add mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (44, 11, 'change_mascota', 'Can change mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (45, 11, 'delete_mascota', 'Can delete mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (46, 11, 'view_mascota', 'Can view mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (47, 12, 'add_cliente', 'Can add cliente');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (48, 12, 'change_cliente', 'Can change cliente');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (49, 12, 'delete_cliente', 'Can delete cliente');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (50, 12, 'view_cliente', 'Can view cliente');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (51, 13, 'add_tenencia', 'Can add relación cliente-mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (52, 13, 'change_tenencia', 'Can change relación cliente-mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (53, 13, 'delete_tenencia', 'Can delete relación cliente-mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (54, 13, 'view_tenencia', 'Can view relación cliente-mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (55, 14, 'add_fotomascota', 'Can add foto de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (56, 14, 'change_fotomascota', 'Can change foto de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (57, 14, 'delete_fotomascota', 'Can delete foto de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (58, 14, 'view_fotomascota', 'Can view foto de mascota');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (59, 15, 'add_session', 'Can add session');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (60, 15, 'change_session', 'Can change session');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (61, 15, 'delete_session', 'Can delete session');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (62, 15, 'view_session', 'Can view session');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (63, 16, 'add_perfil', 'Can add Perfil');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (64, 16, 'change_perfil', 'Can change Perfil');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (65, 16, 'delete_perfil', 'Can delete Perfil');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (66, 16, 'view_perfil', 'Can view Perfil');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (67, 17, 'add_grupopermisos', 'Can add grupo de permisos');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (68, 17, 'change_grupopermisos', 'Can change grupo de permisos');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (69, 17, 'delete_grupopermisos', 'Can delete grupo de permisos');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (70, 17, 'view_grupopermisos', 'Can view grupo de permisos');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (71, 18, 'add_personal', 'Can add integrante del personal');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (72, 18, 'change_personal', 'Can change integrante del personal');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (73, 18, 'delete_personal', 'Can delete integrante del personal');
INSERT INTO "auth_permission" (id, content_type_id, codename, name) VALUES (74, 18, 'view_personal', 'Can view integrante del personal');

-- -------------------------------------------------------------
-- 4. GRUPOS DE USUARIOS (roles) Y SUS PERMISOS
--    Administración, Recepción y Veterinarios
-- -------------------------------------------------------------
INSERT INTO "auth_group" (id, name) VALUES (1, 'Veterinarios');
INSERT INTO "auth_group" (id, name) VALUES (2, 'Recepción');
INSERT INTO "auth_group" (id, name) VALUES (3, 'Administración');
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (1, 1, 38);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (2, 1, 42);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (3, 1, 44);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (4, 1, 46);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (5, 1, 20);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (6, 1, 24);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (7, 1, 26);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (8, 1, 28);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (9, 2, 38);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (10, 2, 42);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (11, 2, 43);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (12, 2, 44);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (13, 2, 46);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (14, 2, 20);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (15, 2, 24);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (16, 2, 25);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (17, 2, 26);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (18, 2, 28);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (19, 3, 17);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (20, 3, 18);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (21, 3, 19);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (22, 3, 20);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (23, 3, 21);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (24, 3, 22);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (25, 3, 23);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (26, 3, 24);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (27, 3, 25);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (28, 3, 26);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (29, 3, 27);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (30, 3, 28);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (31, 3, 29);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (32, 3, 30);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (33, 3, 35);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (34, 3, 36);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (35, 3, 37);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (36, 3, 38);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (37, 3, 39);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (38, 3, 40);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (39, 3, 41);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (40, 3, 42);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (41, 3, 43);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (42, 3, 44);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (43, 3, 45);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (44, 3, 46);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (45, 3, 47);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (46, 3, 48);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (47, 3, 49);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (48, 3, 50);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (49, 3, 51);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (50, 3, 52);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (51, 3, 53);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (52, 3, 54);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (53, 3, 55);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (54, 3, 56);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (55, 3, 57);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (56, 3, 58);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (57, 3, 63);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (58, 3, 64);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (59, 3, 65);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (60, 3, 66);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (61, 3, 67);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (62, 3, 68);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (63, 3, 69);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (64, 3, 70);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (65, 3, 71);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (66, 3, 72);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (67, 3, 73);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (68, 3, 74);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (69, 2, 47);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (70, 2, 48);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (71, 2, 50);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (72, 2, 51);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (73, 2, 52);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (74, 2, 54);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (75, 1, 50);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (76, 1, 54);
INSERT INTO "auth_group_permissions" (id, group_id, permission_id) VALUES (101, 2, 29);

-- -------------------------------------------------------------
-- 5. CATÁLOGOS INICIALES (especies y razas)
-- -------------------------------------------------------------
INSERT INTO "mascotas_especie" (id, nombre) VALUES (1, 'Canino');
INSERT INTO "mascotas_especie" (id, nombre) VALUES (2, 'Felino');
INSERT INTO "mascotas_especie" (id, nombre) VALUES (3, 'Ave');
INSERT INTO "mascotas_especie" (id, nombre) VALUES (4, 'Roedor');
INSERT INTO "mascotas_especie" (id, nombre) VALUES (5, 'Conejo');
INSERT INTO "mascotas_especie" (id, nombre) VALUES (6, 'Reptil');
INSERT INTO "mascotas_especie" (id, nombre) VALUES (7, 'Otro');
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (1, 'Akita Inu', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (2, 'American Staffordshire Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (3, 'Basset Hound', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (4, 'Beagle', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (5, 'Bichón Frisé', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (6, 'Border Collie', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (7, 'Boston Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (8, 'Boxer', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (9, 'Bull Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (10, 'Bulldog Francés', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (11, 'Bulldog Inglés', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (12, 'Cavalier King Charles Spaniel', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (13, 'Chihuahua', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (14, 'Chow Chow', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (15, 'Cocker Spaniel', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (16, 'Collie', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (17, 'Dachshund (salchicha)', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (18, 'Dálmata', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (19, 'Dóberman', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (20, 'Dogo Argentino', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (21, 'Fox Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (22, 'Galgo', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (23, 'Golden Retriever', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (24, 'Gran Danés', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (25, 'Husky Siberiano', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (26, 'Jack Russell Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (27, 'Labrador', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (28, 'Lhasa Apso', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (29, 'Maltés', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (30, 'Mestizo', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (31, 'Pastor Alemán', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (32, 'Pastor Australiano', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (33, 'Pastor Belga Malinois', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (34, 'Pekinés', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (35, 'Pitbull', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (36, 'Pomerania', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (37, 'Poodle', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (38, 'Pug', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (39, 'Quiltro', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (40, 'Rottweiler', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (41, 'Samoyedo', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (42, 'San Bernardo', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (43, 'Schnauzer', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (44, 'Shiba Inu', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (45, 'Shih Tzu', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (46, 'Weimaraner', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (47, 'West Highland White Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (48, 'Yorkshire Terrier', 1);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (49, 'Abisinio', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (50, 'Angora Turco', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (51, 'Azul Ruso', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (52, 'Bengalí', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (53, 'Bosque de Noruega', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (54, 'British Shorthair', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (55, 'Burmés', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (56, 'Devon Rex', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (57, 'Europeo común', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (58, 'Exótico de pelo corto', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (59, 'Himalayo', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (60, 'Maine Coon', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (61, 'Mestizo', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (62, 'Persa', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (63, 'Ragdoll', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (64, 'Sagrado de Birmania', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (65, 'Scottish Fold', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (66, 'Siamés', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (67, 'Sphynx', 2);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (68, 'Agapornis', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (69, 'Cacatúa', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (70, 'Canario', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (71, 'Cotorra', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (72, 'Diamante mandarín', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (73, 'Gallina', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (74, 'Jilguero', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (75, 'Loro', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (76, 'Ninfa', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (77, 'Periquito australiano', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (78, 'Chinchilla', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (79, 'Cuy', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (80, 'Degú', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (81, 'Hámster', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (82, 'Hámster ruso', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (83, 'Jerbo', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (84, 'Rata doméstica', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (85, 'Ratón', 4);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (86, 'Angora', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (87, 'Belier', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (88, 'Cabeza de león', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (89, 'Holandés enano', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (90, 'Mestizo', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (91, 'Mini lop', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (92, 'Rex', 5);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (93, 'Camaleón', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (94, 'Dragón barbudo', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (95, 'Gecko leopardo', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (96, 'Iguana', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (97, 'Pitón bola', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (98, 'Tortuga', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (99, 'Tortuga de agua', 6);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (100, 'Erizo de tierra', 7);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (101, 'Hurón', 7);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (102, 'Pez', 7);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (103, 'Amazona', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (104, 'Caique', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (105, 'Codorniz', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (106, 'Conuro', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (107, 'Diamante de Gould', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (108, 'Eclectus', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (109, 'Ganso', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (110, 'Guacamayo', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (111, 'Guacamayo azul y amarillo', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (112, 'Guacamayo rojo', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (113, 'Lori arcoíris', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (114, 'Loro gris africano', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (115, 'Paloma', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (116, 'Pato', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (117, 'Pavo', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (118, 'Pinzón cebra', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (119, 'Tórtola', 3);
INSERT INTO "mascotas_raza" (id, nombre, especie_id) VALUES (120, 'Tucán', 3);

COMMIT;

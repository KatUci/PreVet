# PreVet

**Sistema predictivo de gestión del riesgo de inasistencia para clínicas veterinarias**

Proyecto APT — Capstone (PTY4614), Portafolio de Título
Instituto Profesional Duoc UC · Escuela de Informática y Telecomunicaciones · Sede Plaza Norte
Ingeniería en Informática

---

## El problema

Las clínicas veterinarias pequeñas gestionan su agenda por WhatsApp, llamada telefónica e
Instagram. Cuando un tutor no llega a su hora, esa cita no se completó pero tampoco fue
cancelada: queda registrada como pendiente para siempre. La clínica no puede medir cuántas
horas pierde, ni cuándo, ni cuánto le cuesta.

## La propuesta

Construir un sistema de gestión para clínicas veterinarias y extenderlo con un módulo que:

1. **Formaliza** el proceso de agendamiento (modelado en BPMN)
2. **Estructura** el registro de la inasistencia, hoy inexistente en el modelo de datos
3. **Mide** la tasa de inasistencia y su impacto económico
4. **Predice** la probabilidad de que cada hora agendada se pierda
5. **Recomienda** una acción concreta para cada hora en riesgo

El componente innovador es el paso de **recordatorios uniformes a predicción diferenciada
por reserva**: las soluciones disponibles en el mercado chileno envían el mismo recordatorio
a todos los clientes, sin estimar el riesgo de cada caso.

## Contexto

Clínicas veterinarias de Lo Pinto y Batuco, zona norte de la Región Metropolitana.
Caso principal de estudio: Clínica Veterinaria Clan.

## Equipo

| Integrante | Rol |
|---|---|
| Katalina Mora Quiñones | Analista de datos y gestora del proyecto |
| Uciell Madrid | Analista funcional y encargada de calidad |

Docente: Juan Alberto Gana Reyes · Sección CAPSTONE_007V

## Delimitación de la autoría

El sistema que vive en la carpeta `sistema/` fue construido desde cero durante esta
asignatura, y su historial de commits lo registra paso a paso: creación del proyecto,
modelo de datos y tablero de indicadores.

Existe un sistema veterinario anterior, desarrollado por Katalina Mora en conjunto con
una colaboradora externa antes de iniciar el Capstone. No forma parte de esta entrega y
no se publica en el repositorio: se conservó únicamente como material de consulta, y de
su análisis surgió el hallazgo que da origen al proyecto, a saber, que su modelo de citas
no contemplaba el estado de inasistencia. El diseño visual de la interfaz (paleta, barra
lateral y componentes) se reutiliza de ese trabajo previo; la lógica de los modelos, los
indicadores y el tablero es desarrollo propio del equipo.

## Estructura del repositorio

```
Fase 1/
├── Evidencias Individuales/
│   ├── Katalina_Mora_1.1 · 1.2 · 1.3
│   └── Uciell_Madrid_1.1 · 1.2 · 1.3
└── Evidencias Grupales/
    ├── 1.4_APT122_FormativaFase1.docx       Pauta de evaluación
    ├── 1.5_GuiaEstudiante_...docx           Definición del Proyecto APT
    ├── Informe_Tecnico_PreVet_Fase1.docx    Informe técnico
    └── Presentacion_PreVet_Fase1.pptx       Presentación del proyecto

sistema/                                     Código fuente
├── usuarios/    perfiles y roles
├── mascotas/    especies, razas y pacientes
├── citas/       tipos de atención, horarios y citas
├── core/        tablero de indicadores
└── templates/   interfaz web
```

## Estado del desarrollo

El sistema está operativo. Sobre un conjunto de datos de ejemplo de 255 citas
distribuidas en noventa días, el tablero reporta una tasa de inasistencia del 17,3 %,
equivalente a $1.061.000 en ingresos no percibidos, y muestra la distribución de faltas
por día de la semana.

Para levantarlo:

```bash
cd sistema
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_demo
python manage.py runserver
```

## Tecnologías

Django 5.0 · SQLite · SQL · Power BI · BPMN (Bizagi Modeler) · Figma ·
Katalon Studio · Postman · Git

## Metodología

CRISP-DM para el desarrollo analítico, complementado con un marco ágil de gestión
en incrementos de dos semanas.

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

Extender el sistema de gestión veterinaria **Huellitas** con un módulo que:

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

El sistema base **Huellitas** (módulos de usuarios, mascotas, agenda, historial clínico,
vacunas, síntomas, inventario y adopciones) fue desarrollado con anterioridad a esta
asignatura por Katalina Mora en conjunto con una colaboradora externa al equipo.

El aporte de este Proyecto APT, desarrollado íntegramente por el equipo, corresponde al
módulo de gestión del riesgo de inasistencia.

## Estructura del repositorio

```
Fase 1/
├── Evidencias Individuales/
│   ├── Katalina_Mora_1.1_APT122_AutoevaluacionCompetenciasFase1.docx
│   ├── Katalina_Mora_1.2_APT122_DiarioReflexionFase1.docx
│   ├── Uciell_Madrid_1.1_APT122_AutoevaluacionCompetenciasFase1.docx
│   └── Uciell_Madrid_1.2_APT122_DiarioReflexionFase1.docx
└── Evidencias Grupales/
    ├── 1.4_APT122_FormativaFase1.docx          Informe técnico
    ├── 1.5_GuiaEstudiante_Fase 1_...docx       Definición del Proyecto APT
    └── Presentacion_PreVet_Fase1.pptx         Presentación del proyecto
```

## Tecnologías

Django 4.2 · SQLite · SQL · Power BI · BPMN (Bizagi Modeler) · Figma ·
Katalon Studio · Postman · Git

## Metodología

CRISP-DM para el desarrollo analítico, complementado con un marco ágil de gestión
en incrementos de dos semanas.

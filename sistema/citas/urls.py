from django.urls import path

from . import atencion, calendario, configuracion, panel, views

urlpatterns = [
    path('', views.listado, name='citas'),
    path('nueva/', views.agendar, name='agendar'),
    path('hoy/', panel.panel_dia, name='panel_dia'),
    path('exportar/', views.exportar, name='citas_exportar'),
    path('<int:pk>/no-asistio/', views.marcar_no_asistio, name='marcar_no_asistio'),

    path('calendario/', calendario.calendario, name='calendario'),
    path('calendario/eventos/', calendario.eventos, name='calendario_eventos'),
    path('<int:pk>/detalle/', calendario.detalle, name='cita_detalle'),
    path('<int:pk>/llego/', calendario.marcar_llegada, name='cita_llego'),
    path('<int:pk>/atender/', atencion.atender, name='cita_atender'),
    path('<int:pk>/cancelar/', calendario.cancelar, name='cita_cancelar'),
    path('<int:pk>/reagendar/', calendario.reagendar, name='cita_reagendar'),
    path('<int:pk>/editar/', views.editar, name='cita_editar'),

    path('tipos/', configuracion.tipos_listado, name='tipos_atencion'),
    path('tipos/nuevo/', configuracion.tipo_formulario, name='tipo_nuevo'),
    path('tipos/<int:pk>/', configuracion.tipo_formulario, name='tipo_editar'),
    path('tipos/<int:pk>/eliminar/', configuracion.tipo_eliminar, name='tipo_eliminar'),
    path('horarios/', configuracion.horarios_listado, name='horarios'),
    path('horarios/nuevo/', configuracion.horario_formulario, name='horario_nuevo'),
    path('horarios/<int:pk>/', configuracion.horario_formulario, name='horario_editar'),
    path('horarios/<int:pk>/eliminar/', configuracion.horario_eliminar, name='horario_eliminar'),
]

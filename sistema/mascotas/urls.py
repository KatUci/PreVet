from django.urls import path

from . import clientes, configuracion, fotos, views

urlpatterns = [
    path('', views.listado, name='mascotas'),
    path('<int:pk>/', views.ficha, name='mascota_ficha'),
    path('<int:pk>/editar/', clientes.mascota_editar, name='mascota_editar'),
    path('<int:pk>/estado/', clientes.mascota_estado, name='mascota_estado'),
    path('<int:pk>/foto/', fotos.ver_foto, name='mascota_foto'),
    path('tipos/', configuracion.especies_listado, name='especies'),
    path('tipos/nuevo/', configuracion.especie_formulario, name='especie_nueva'),
    path('tipos/<int:pk>/', configuracion.especie_formulario, name='especie_editar'),
    path('tipos/<int:pk>/eliminar/', configuracion.especie_eliminar, name='especie_eliminar'),
    path('etiquetas/', configuracion.etiquetas_listado, name='etiquetas'),
    path('etiquetas/nueva/', configuracion.etiqueta_formulario, name='etiqueta_nueva'),
    path('etiquetas/<int:pk>/', configuracion.etiqueta_formulario, name='etiqueta_editar'),
    path('etiquetas/<int:pk>/eliminar/', configuracion.etiqueta_eliminar, name='etiqueta_eliminar'),
    path('<int:pk>/etiquetas/', clientes.mascota_etiquetas, name='mascota_etiquetas'),
    path('razas/', configuracion.razas_listado, name='razas'),
    path('razas/nueva/', configuracion.raza_formulario, name='raza_nueva'),
    path('razas/<int:pk>/', configuracion.raza_formulario, name='raza_editar'),
    path('razas/<int:pk>/eliminar/', configuracion.raza_eliminar, name='raza_eliminar'),
    path('<int:pk>/foto/subir/', fotos.subir_foto, name='mascota_foto_subir'),
    path('<int:pk>/foto/quitar/', fotos.quitar_foto, name='mascota_foto_quitar'),
]
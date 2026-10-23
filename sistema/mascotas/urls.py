from django.urls import path

from . import clientes, configuracion, fotos, views

urlpatterns = [
    path('', views.listado, name='mascotas'),
    path('<int:pk>/editar/', clientes.mascota_editar, name='mascota_editar'),
    path('<int:pk>/estado/', clientes.mascota_estado, name='mascota_estado'),
    path('<int:pk>/foto/', fotos.ver_foto, name='mascota_foto'),
    path('tipos/', configuracion.especies_listado, name='especies'),
    path('tipos/nuevo/', configuracion.especie_formulario, name='especie_nueva'),
    path('tipos/<int:pk>/', configuracion.especie_formulario, name='especie_editar'),
    path('tipos/<int:pk>/eliminar/', configuracion.especie_eliminar, name='especie_eliminar'),
    path('razas/', configuracion.razas_listado, name='razas'),
    path('razas/nueva/', configuracion.raza_formulario, name='raza_nueva'),
    path('razas/<int:pk>/', configuracion.raza_formulario, name='raza_editar'),
    path('razas/<int:pk>/eliminar/', configuracion.raza_eliminar, name='raza_eliminar'),
    path('<int:pk>/foto/subir/', fotos.subir_foto, name='mascota_foto_subir'),
    path('<int:pk>/foto/quitar/', fotos.quitar_foto, name='mascota_foto_quitar'),
]
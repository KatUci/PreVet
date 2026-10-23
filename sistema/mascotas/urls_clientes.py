from django.urls import path

from . import clientes, directorio

urlpatterns = [
    path('', directorio.clientes_listado, name='clientes'),
    path('<int:pk>/', directorio.cliente_ficha, name='cliente_ficha'),
    path('<int:pk>/editar/', clientes.cliente_editar, name='cliente_editar'),
    path('<int:pk>/estado/', clientes.cliente_estado, name='cliente_estado'),
    path('nuevo/', clientes.cliente_nuevo, name='cliente_nuevo'),
    path('<int:cliente_pk>/mascotas/nueva/', clientes.mascota_nueva, name='mascota_nueva'),
]

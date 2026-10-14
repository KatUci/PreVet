from django.urls import path

from . import clientes

urlpatterns = [
    path('nuevo/', clientes.cliente_nuevo, name='cliente_nuevo'),
    path('<int:cliente_pk>/mascotas/nueva/', clientes.mascota_nueva, name='mascota_nueva'),
]

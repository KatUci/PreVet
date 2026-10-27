from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='portal'),
    path('datos/', views.mis_datos, name='portal_datos'),
    path('pedir-hora/', views.pedir_hora, name='portal_pedir_hora'),
    path('clave/', views.solo_tutores(views.CambiarClave.as_view()), name='portal_clave'),
    path('mascotas/nueva/', views.mascota_nueva, name='portal_mascota_nueva'),
    path('mascotas/<int:pk>/', views.mascota_editar, name='portal_mascota_editar'),
    path('mascotas/<int:pk>/foto/', views.mascota_foto, name='portal_mascota_foto'),
    path('mascotas/<int:pk>/foto/subir/', views.mascota_foto_subir, name='portal_mascota_foto_subir'),
]

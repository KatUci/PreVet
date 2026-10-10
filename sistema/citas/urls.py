from django.urls import path

from . import views

urlpatterns = [
    path('', views.listado, name='citas'),
    path('<int:pk>/no-asistio/', views.marcar_no_asistio, name='marcar_no_asistio'),
]
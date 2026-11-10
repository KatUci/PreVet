from django.urls import path

from . import importar, views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('indicadores/', views.indicadores, name='indicadores'),
    path('buscar/', views.buscar, name='buscar'),
    path('riesgo/', views.riesgo, name='riesgo'),
    path('riesgo/exportar/', views.riesgo_exportar, name='riesgo_exportar'),
    path('importar/', importar.importar, name='importar'),
    path('importar/plantilla/<str:tipo>/', importar.plantilla, name='importar_plantilla'),
]
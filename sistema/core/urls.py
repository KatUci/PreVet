from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('indicadores/', views.indicadores, name='indicadores'),
    path('riesgo/', views.riesgo, name='riesgo'),
]
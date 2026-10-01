from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('riesgo/', views.riesgo, name='riesgo'),
]
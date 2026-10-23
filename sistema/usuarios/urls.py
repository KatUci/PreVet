from django.urls import path

from . import views

urlpatterns = [
    path('personal/', views.personal_listado, name='personal'),
    path('personal/nuevo/', views.personal_formulario, name='personal_nuevo'),
    path('personal/<int:pk>/', views.personal_formulario, name='personal_editar'),

    path('grupos/', views.grupos_listado, name='grupos'),
    path('grupos/nuevo/', views.grupo_formulario, name='grupo_nuevo'),
    path('grupos/<int:pk>/', views.grupo_formulario, name='grupo_editar'),
    path('grupos/<int:pk>/eliminar/', views.grupo_eliminar, name='grupo_eliminar'),
]

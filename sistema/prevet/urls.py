from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

# Textos del panel de administración (reemplazan a los de Django).
admin.site.site_header = 'PreVet'
admin.site.site_title = 'PreVet'
admin.site.index_title = 'Panel de administración'

urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    path('citas/', include('citas.urls')),
    path('mascotas/', include('mascotas.urls')),
    path('administracion/', include('usuarios.urls')),
    path('', include('core.urls')),
]
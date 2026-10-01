from django.contrib import admin

from .models import Especie, Raza, Mascota


@admin.register(Especie)
class EspecieAdmin(admin.ModelAdmin):
    list_display = ('nombre',)


@admin.register(Raza)
class RazaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especie')
    list_filter = ('especie',)


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especie', 'raza', 'sexo', 'dueno', 'activo')
    list_filter = ('especie', 'sexo', 'activo')
    search_fields = ('nombre', 'dueno__username')
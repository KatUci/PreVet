from django.contrib import admin

from .models import Cliente, Especie, Mascota, Raza, Tenencia


class RazaInline(admin.TabularInline):
    model = Raza
    extra = 1


@admin.register(Especie)
class EspecieAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad_razas')
    inlines = [RazaInline]

    @admin.display(description='Razas')
    def cantidad_razas(self, obj):
        return obj.razas.count()


@admin.register(Raza)
class RazaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especie')
    list_filter = ('especie',)


class MascotasDelClienteInline(admin.TabularInline):
    """Dentro de la ficha del cliente: sus mascotas y qué relación tiene."""
    model = Tenencia
    extra = 1
    autocomplete_fields = ['mascota']
    verbose_name = 'mascota'
    verbose_name_plural = 'mascotas del cliente'


class ClientesDeLaMascotaInline(admin.TabularInline):
    """Dentro de la ficha de la mascota: sus clientes."""
    model = Tenencia
    extra = 1
    autocomplete_fields = ['cliente']
    verbose_name = 'cliente'
    verbose_name_plural = 'clientes de la mascota'


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('rut_formateado', 'nombre_completo', 'telefono', 'email', 'cantidad_mascotas', 'activo')
    list_filter = ('activo',)
    search_fields = ('rut', 'nombres', 'apellidos', 'email')
    inlines = [MascotasDelClienteInline]

    @admin.display(description='RUT', ordering='rut')
    def rut_formateado(self, obj):
        return obj.rut_formateado

    @admin.display(description='Nombre', ordering='apellidos')
    def nombre_completo(self, obj):
        return obj.nombre_completo

    @admin.display(description='Mascotas')
    def cantidad_mascotas(self, obj):
        return obj.mascotas.count()


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especie', 'raza', 'sexo', 'responsable', 'activo')
    list_filter = ('especie', 'sexo', 'activo')
    search_fields = ('nombre', 'tutores__nombres', 'tutores__apellidos', 'tutores__rut')
    inlines = [ClientesDeLaMascotaInline]

    @admin.display(description='Responsable')
    def responsable(self, obj):
        cliente = obj.responsable
        return cliente.nombre_completo if cliente else '—'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tenencias__cliente')

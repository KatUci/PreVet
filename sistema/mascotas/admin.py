from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Cliente, Especie, FotoMascota, Mascota, Raza, Tenencia


class RazaInline(admin.TabularInline):
    model = Raza
    extra = 1


@admin.register(Especie)
class EspecieAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad_razas')
    search_fields = ('nombre',)
    inlines = [RazaInline]

    @admin.display(description='Razas')
    def cantidad_razas(self, obj):
        return obj.razas.count()


@admin.register(Raza)
class RazaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especie')
    list_filter = ('especie',)
    search_fields = ('nombre',)


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
    list_display = ('rut_formateado', 'nombre_completo', 'telefono', 'canal_preferido', 'comuna',
                    'cantidad_mascotas', 'consentimiento_datos', 'activo')
    list_filter = ('activo', 'canal_preferido', 'consentimiento_datos', 'region', 'comuna')
    search_fields = ('rut', 'nombres', 'apellidos', 'email', 'telefono', 'mascotas__nombre')
    readonly_fields = ('fecha_registro', 'fecha_consentimiento')
    list_per_page = 30
    inlines = [MascotasDelClienteInline]
    fieldsets = (
        ('Identificación', {'fields': ('rut', 'nombres', 'apellidos', 'activo')}),
        ('Contacto', {'fields': ('telefono', 'email', 'canal_preferido')}),
        ('Dirección', {'fields': ('direccion', 'comuna', 'region')}),
        ('Emergencia', {'fields': ('contacto_emergencia', 'telefono_emergencia')}),
        ('Datos personales (Ley 19.628)', {'fields': ('consentimiento_datos', 'fecha_consentimiento',
                                                      'fecha_registro')}),
    )

    @admin.display(description='RUT', ordering='rut')
    def rut_formateado(self, obj):
        return obj.rut_formateado

    @admin.display(description='Nombre', ordering='apellidos')
    def nombre_completo(self, obj):
        return obj.nombre_completo

    @admin.display(description='Mascotas')
    def cantidad_mascotas(self, obj):
        return obj.mascotas.count()


class FotoInline(admin.StackedInline):
    """La foto se sube desde PreVet (allí se achica); aquí solo se ve o se quita."""
    model = FotoMascota
    extra = 0
    max_num = 0
    can_delete = True
    fields = ('vista_previa', 'actualizada', 'subida_por')
    readonly_fields = ('vista_previa', 'actualizada', 'subida_por')
    verbose_name_plural = 'foto (para subir o cambiarla, usa la pantalla de Mascotas)'

    @admin.display(description='Foto')
    def vista_previa(self, obj):
        url = reverse('mascota_foto', args=[obj.mascota_id])
        return format_html('<img src="{}?v={}" style="max-height:180px;border-radius:10px">', url,
                           obj.mascota.foto_version)


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'nombre', 'especie', 'raza', 'sexo', 'responsable', 'microchip', 'peso_kg',
                    'activo')
    list_display_links = ('miniatura', 'nombre')
    list_filter = ('especie', 'sexo', 'tiene_microchip', 'esterilizada', 'activo')
    search_fields = ('nombre', 'microchip', 'tutores__nombres', 'tutores__apellidos', 'tutores__rut')
    readonly_fields = ('fecha_registro', 'foto_version')
    list_per_page = 30
    inlines = [ClientesDeLaMascotaInline, FotoInline]
    fieldsets = (
        ('Datos básicos', {'fields': ('nombre', 'especie', 'raza', 'sexo', 'fecha_nacimiento', 'activo')}),
        ('Identificación', {'fields': ('tiene_microchip', 'microchip', 'color')}),
        ('Salud', {'fields': ('peso_kg', 'esterilizada', 'alergias', 'condiciones', 'observaciones')}),
        ('Registro', {'fields': ('fecha_registro', 'foto_version'), 'classes': ('collapse',)}),
    )

    @admin.display(description='')
    def miniatura(self, obj):
        if obj.foto_version:
            url = reverse('mascota_foto', args=[obj.pk])
            return format_html('<img src="{}?v={}" style="width:36px;height:36px;object-fit:cover;'
                               'border-radius:50%">', url, obj.foto_version)
        return obj.especie.emoji

    @admin.display(description='Responsable')
    def responsable(self, obj):
        cliente = obj.responsable
        return cliente.nombre_completo if cliente else '—'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('especie', 'raza').prefetch_related('tenencias__cliente')


@admin.register(Tenencia)
class TenenciaAdmin(admin.ModelAdmin):
    list_display = ('mascota', 'cliente', 'relacion', 'es_principal')
    list_filter = ('relacion', 'es_principal')
    search_fields = ('mascota__nombre', 'cliente__nombres', 'cliente__apellidos', 'cliente__rut')
    autocomplete_fields = ['mascota', 'cliente']

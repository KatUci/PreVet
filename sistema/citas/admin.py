from django.contrib import admin
from django.utils import timezone

from .models import Cita, HorarioAtencion, TipoAtencion


@admin.register(TipoAtencion)
class TipoAtencionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'duracion_minutos', 'precio', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(admin.ModelAdmin):
    list_display = ('veterinario', 'dia_semana', 'hora_inicio', 'hora_fin', 'activo')
    list_filter = ('dia_semana', 'veterinario', 'activo')
    ordering = ('veterinario__first_name', 'dia_semana', 'hora_inicio')


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'hora', 'mascota', 'cliente', 'veterinario', 'tipo_atencion', 'estado',
                    'dias_anticipacion')
    list_filter = ('estado', 'fecha', 'veterinario', 'tipo_atencion')
    search_fields = ('mascota__nombre', 'cliente__nombres', 'cliente__apellidos', 'cliente__rut')
    date_hierarchy = 'fecha'
    autocomplete_fields = ['mascota', 'cliente']
    readonly_fields = ('fecha_creacion', 'hora_llegada', 'cancelada_por', 'fecha_cancelacion',
                       'fecha_marcada_no_asistio')
    list_per_page = 40
    fieldsets = (
        ('Cita', {'fields': ('fecha', 'hora', 'veterinario', 'tipo_atencion', 'estado', 'notas')}),
        ('Paciente', {'fields': ('mascota', 'cliente')}),
        ('Seguimiento', {'fields': ('hora_llegada', 'fecha_marcada_no_asistio', 'motivo_cancelacion',
                                    'cancelada_por', 'fecha_cancelacion', 'fecha_creacion')}),
    )
    actions = ['marcar_no_asistio']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('mascota', 'cliente', 'veterinario', 'tipo_atencion')

    @admin.action(description="Marcar como NO ASISTIÓ (solo pendientes de hoy o antes)")
    def marcar_no_asistio(self, request, queryset):
        # Misma regla que en PreVet: no se marca la inasistencia de una cita futura.
        actualizadas = (queryset.filter(estado='pendiente', fecha__lte=timezone.localdate())
                        .update(estado='no_asistio', fecha_marcada_no_asistio=timezone.now()))
        self.message_user(request, f"{actualizadas} cita(s) marcadas como no asistidas.")

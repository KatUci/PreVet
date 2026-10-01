from django.contrib import admin

from .models import TipoAtencion, HorarioAtencion, Cita


@admin.register(TipoAtencion)
class TipoAtencionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'duracion_minutos', 'precio', 'activo')
    list_filter = ('activo',)


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(admin.ModelAdmin):
    list_display = ('veterinario', 'dia_semana', 'hora_inicio', 'hora_fin', 'activo')
    list_filter = ('dia_semana', 'veterinario', 'activo')


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'hora', 'mascota', 'veterinario',
                    'tipo_atencion', 'estado', 'dias_anticipacion')
    list_filter = ('estado', 'fecha', 'veterinario', 'tipo_atencion')
    search_fields = ('mascota__nombre',)
    date_hierarchy = 'fecha'

    actions = ['marcar_no_asistio']

    @admin.action(description="Marcar como NO ASISTIÓ")
    def marcar_no_asistio(self, request, queryset):
        from django.utils import timezone
        actualizadas = queryset.update(
            estado='no_asistio',
            fecha_marcada_no_asistio=timezone.now(),
        )
        self.message_user(request, f"{actualizadas} cita(s) marcadas como no asistidas.")
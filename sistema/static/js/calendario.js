// Calendario de citas con FullCalendar: vistas Día, Semana, Mes y Agenda.
(function () {
    var el = document.getElementById('calendario');
    if (!el || !window.FullCalendar) return;

    var filtroVet = document.getElementById('filtroVet');
    var panel = document.getElementById('panelCita');
    var fondo = document.getElementById('panelFondo');
    var contenido = document.getElementById('panelContenido');

    // En pantallas chicas la semana no cabe: se parte en la vista Agenda.
    var angosto = window.matchMedia('(max-width: 700px)').matches;
    var vistaInicial = el.dataset.vista || (angosto ? 'listWeek' : 'timeGridWeek');

    // Crea un elemento con texto (sin HTML), para no insertar contenido ajeno.
    function nodo(etiqueta, clase, texto) {
        var n = document.createElement(etiqueta);
        n.className = clase;
        n.textContent = texto;
        return n;
    }

    var calendario = new FullCalendar.Calendar(el, {
        locale: 'es',
        initialView: vistaInicial,
        initialDate: el.dataset.fecha || undefined,
        headerToolbar: {
            left: 'title',
            right: 'prev,today,next timeGridDay,timeGridWeek,dayGridMonth,listWeek'
        },
        buttonText: { today: 'Hoy', day: 'Día', week: 'Semana', month: 'Mes', list: 'Agenda' },
        slotMinTime: '08:00:00',
        slotMaxTime: '20:00:00',
        slotDuration: '00:30:00',
        slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        allDaySlot: false,
        nowIndicator: true,
        expandRows: true,
        // Las atenciones cortas (20 minutos) igual muestran sus dos líneas.
        eventMinHeight: 48,
        height: 'auto',
        dayMaxEvents: 3,
        noEventsText: 'No hay citas en este rango.',

        // Cabecera de cada día: el nombre corto arriba y el número en un círculo.
        dayHeaderContent: function (arg) {
            if (arg.view.type.indexOf('timeGrid') !== 0) return arg.text;
            var caja = document.createElement('div');
            caja.className = 'cab-dia';
            caja.appendChild(nodo('span', 'cab-nombre',
                arg.date.toLocaleDateString('es-CL', { weekday: 'short' }).replace('.', '')));
            caja.appendChild(nodo('span', 'cab-numero' + (arg.isToday ? ' hoy' : ''),
                String(arg.date.getDate())));
            return { domNodes: [caja] };
        },

        // Contenido de cada cita: mascota en negrita y, debajo, hora y atención.
        // En la vista Día, que es ancha, el cliente y el profesional van a la
        // derecha como etiquetas, para que todo quede dentro del recuadro.
        eventContent: function (arg) {
            var p = arg.event.extendedProps;
            var tipo = arg.view.type;
            var hora = FullCalendar.formatDate(arg.event.start,
                { hour: '2-digit', minute: '2-digit', hour12: false, locale: 'es' });

            var titulo = nodo('div', 'ev-titulo', p.emoji + ' ' + p.mascota);
            if (p.riesgo === 'alto') titulo.appendChild(nodo('span', 'ev-alerta', ' ⚠'));

            var caja = document.createElement('div');
            caja.className = 'ev-caja';

            if (tipo === 'dayGridMonth') {
                titulo.prepend(nodo('span', 'ev-hora-inline', hora + ' '));
                caja.appendChild(titulo);
            } else if (tipo === 'timeGridDay') {
                caja.classList.add('ev-dia');
                var principal = document.createElement('div');
                principal.className = 'ev-principal';
                principal.appendChild(titulo);
                principal.appendChild(nodo('div', 'ev-detalle', hora + ' · ' + p.atencion));
                var meta = document.createElement('div');
                meta.className = 'ev-meta';
                meta.appendChild(nodo('span', 'ev-chip', '👤 ' + p.cliente));
                meta.appendChild(nodo('span', 'ev-chip', '🩺 ' + p.profesional));
                caja.appendChild(principal);
                caja.appendChild(meta);
            } else {
                caja.appendChild(titulo);
                // En la Agenda la hora ya aparece en su propia columna.
                var esLista = tipo.indexOf('list') === 0;
                caja.appendChild(nodo('div', 'ev-detalle', esLista ? p.atencion : hora + ' · ' + p.atencion));
                if (esLista) caja.appendChild(nodo('div', 'ev-detalle', p.cliente + ' · ' + p.profesional));
            }
            return { domNodes: [caja] };
        },

        events: function (info, ok, error) {
            var url = el.dataset.eventos +
                '?start=' + info.startStr.slice(0, 10) +
                '&end=' + info.endStr.slice(0, 10) +
                '&veterinario=' + encodeURIComponent(filtroVet.value);
            fetch(url, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(ok)
                .catch(error);
        },

        eventDidMount: function (info) {
            var p = info.event.extendedProps;
            info.el.title = info.event.title + '\n' + p.cliente + ' · ' + p.profesional + '\n' + p.estado;
        },

        loading: function (cargando) {
            document.getElementById('calCargando').hidden = !cargando;
        },

        eventClick: function (info) {
            abrirPanel(info.event.id);
        },

        // Guarda en la dirección la vista y la fecha, para volver al mismo
        // lugar después de atender, cancelar o reagendar.
        datesSet: function () { guardarEnDireccion(); }
    });
    calendario.render();

    function guardarEnDireccion() {
        if (!calendario) return;
        var params = new URLSearchParams(window.location.search);
        params.set('vista', calendario.view.type);
        params.set('fecha', calendario.getDate().toISOString().slice(0, 10));
        if (filtroVet.value) params.set('veterinario', filtroVet.value);
        else params.delete('veterinario');
        history.replaceState(null, '', '?' + params.toString());
    }

    filtroVet.addEventListener('change', function () {
        calendario.refetchEvents();
        guardarEnDireccion();
    });

    // ---------- Panel lateral con el detalle ----------
    function abrirPanel(id) {
        contenido.innerHTML = '<p class="ayuda">Cargando…</p>';
        panel.classList.add('abierto');
        panel.setAttribute('aria-hidden', 'false');
        fondo.hidden = false;

        fetch('/citas/' + id + '/detalle/', { credentials: 'same-origin' })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                contenido.innerHTML = html;
                // Después de actuar, se vuelve a esta misma vista del calendario.
                contenido.querySelectorAll('.volver-aqui').forEach(function (input) {
                    input.value = window.location.pathname + window.location.search;
                });
            });
    }

    function cerrarPanel() {
        panel.classList.remove('abierto');
        panel.setAttribute('aria-hidden', 'true');
        fondo.hidden = true;
    }

    document.getElementById('panelCerrar').addEventListener('click', cerrarPanel);
    fondo.addEventListener('click', cerrarPanel);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') cerrarPanel();
    });
})();

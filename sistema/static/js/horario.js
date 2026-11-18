// Agendar y reagendar: al elegir profesional y fecha se avisa al tiro si ese
// día atiende, y la lista de horas queda solo con las libres.
// Sin JavaScript igual funciona: el servidor valida al guardar.
(function () {
    var form = document.querySelector('form[data-disponibles]');
    if (!form) return;
    var vet = form.querySelector('[name=veterinario]');
    var fecha = form.querySelector('[name=fecha]');
    var hora = form.querySelector('select[name=hora]');
    var aviso = document.getElementById('avisoHorario');
    if (!vet || !fecha || !hora || !aviso) return;

    var originales = Array.prototype.map.call(hora.options, function (o) { return [o.value, o.text]; });
    var pedido = 0;

    function opciones(lista, elegida) {
        hora.innerHTML = '';
        lista.forEach(function (par) {
            hora.add(new Option(par[1], par[0], false, par[0] === elegida));
        });
    }

    function mostrar(tipo, texto) {
        aviso.className = 'alerta alerta-' + tipo;
        aviso.textContent = texto;
        aviso.hidden = false;
    }

    function revisar() {
        var elegida = hora.value;
        if (!vet.value || !fecha.value) {
            aviso.hidden = true;
            opciones(originales, elegida);
            return;
        }
        var params = new URLSearchParams({ veterinario: vet.value, fecha: fecha.value });
        if (form.dataset.excepto) params.set('excepto', form.dataset.excepto);
        if (form.dataset.futuras) params.set('futuras', '1');
        var este = ++pedido;

        fetch(form.dataset.disponibles + '?' + params)
            .then(function (r) { return r.json(); })
            .then(function (datos) {
                if (este !== pedido) return;          // llegó la respuesta de una elección anterior
                if (datos.error) { aviso.hidden = true; return; }
                var vacio = datos.libres.length ? 'Elige la hora' : 'Sin horas libres';
                opciones([['', vacio]].concat(datos.libres.map(function (h) { return [h, h]; })), elegida);
                mostrar(datos.libres.length ? 'info' : 'warning', datos.mensaje);
            })
            .catch(function () { aviso.hidden = true; });
    }

    // Sábado y domingo solo se atienden urgencias: si se elige otra atención
    // para ese día, se avisa al tiro con una ventana (el servidor igual lo revisa).
    var tipo = form.querySelector('[name=tipo_atencion]');
    var datosDosis = document.getElementById('dosisMascotas');
    var dosis = datosDosis ? JSON.parse(datosDosis.textContent) : {};   // {mascota: [fechas]}
    var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

    function avisarFinDeSemana() {
        if (!tipo || !tipo.value || !fecha.value) return;
        var nombre = tipo.options[tipo.selectedIndex].text.replace(/\s*\(.*\)\s*$/, '');
        var dia = new Date(fecha.value + 'T12:00:00');
        var esFinDeSemana = dia.getDay() === 0 || dia.getDay() === 6;
        if (!esFinDeSemana || nombre.toLowerCase().indexOf('urgencia') !== -1) return;
        // La vacuna sí se puede si justo ese día le toca la próxima dosis a la mascota.
        var elegida = form.querySelector('[name=mascota]:checked');
        if (nombre.toLowerCase().indexOf('vacuna') !== -1 && elegida &&
            (dosis[elegida.value] || []).indexOf(fecha.value) !== -1) return;

        var partes = fecha.value.split('-');
        var fondo = document.createElement('div');
        fondo.className = 'modal-fondo modal-aviso';
        fondo.innerHTML =
            '<div class="modal" role="alertdialog" aria-modal="true" aria-labelledby="tituloAviso">' +
            '<div class="modal-aviso-icono">☀️</div>' +
            '<h3 id="tituloAviso"></h3><p></p>' +
            '<div class="modal-acciones"><button type="button" class="btn btn-primario">Elegir otro día</button></div></div>';
        fondo.querySelector('h3').textContent = 'No se puede agendar ' + nombre + ' ese día';
        fondo.querySelector('p').textContent = 'El ' + DIAS[dia.getDay()] + ' ' + partes[2] + '/' + partes[1] +
            ' solo se atienden urgencias, y vacunas si ese día le toca la próxima dosis a la mascota. ' +
            'Las consultas, controles y exámenes se agendan de lunes a viernes.';
        document.body.appendChild(fondo);
        var boton = fondo.querySelector('button');
        boton.focus();
        boton.addEventListener('click', function () {
            fondo.remove();
            fecha.value = '';           // se borra la fecha para que elija un día de semana
            revisar();
            fecha.focus();
        });
    }

    if (tipo) tipo.addEventListener('change', avisarFinDeSemana);
    form.querySelectorAll('[name=mascota]').forEach(function (m) { m.addEventListener('change', avisarFinDeSemana); });
    fecha.addEventListener('change', avisarFinDeSemana);
    vet.addEventListener('change', revisar);
    fecha.addEventListener('change', revisar);
    revisar();   // si el formulario vuelve con errores, ya trae profesional y fecha
})();

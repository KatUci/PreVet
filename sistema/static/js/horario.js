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

    vet.addEventListener('change', revisar);
    fecha.addEventListener('change', revisar);
    revisar();   // si el formulario vuelve con errores, ya trae profesional y fecha
})();

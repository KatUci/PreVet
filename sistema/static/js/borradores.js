// Borradores: si se llena un formulario y se va a otra sección (por ejemplo
// a "Mis recetas"), al volver lo escrito sigue ahí. Se guarda en el navegador
// solo mientras la pestaña está abierta (sessionStorage) y se borra al guardar,
// al cancelar o al cerrar sesión. Nunca se guardan contraseñas ni archivos.
(function () {
    var almacen;
    try { almacen = window.sessionStorage; } catch (e) { return; }
    if (!almacen) return;

    var PREFIJO = 'prevet-borrador:';
    var NO_GUARDAR = ['hidden', 'password', 'file', 'submit', 'button', 'reset'];

    function campos(form) {
        return Array.prototype.filter.call(form.elements, function (el) {
            return el.name && NO_GUARDAR.indexOf(el.type) === -1 &&
                   el.name !== 'csrfmiddlewaretoken' && el.name !== 'next';
        });
    }

    function leer(form) {
        var datos = {};
        campos(form).forEach(function (el) {
            if (el.type === 'radio') {
                if (el.checked) datos[el.name] = el.value;
            } else if (el.type === 'checkbox') {
                datos[el.name] = datos[el.name] || [];
                if (el.checked) datos[el.name].push(el.value);
            } else if (el.multiple) {
                datos[el.name] = Array.prototype.filter.call(el.options, function (o) { return o.selected; })
                                                   .map(function (o) { return o.value; });
            } else {
                datos[el.name] = el.value;
            }
        });
        return datos;
    }

    function rellenar(form, datos) {
        campos(form).forEach(function (el) {
            if (!(el.name in datos)) return;
            var valor = datos[el.name];
            if (el.type === 'radio') el.checked = el.value === valor;
            else if (el.type === 'checkbox') el.checked = valor.indexOf(el.value) !== -1;
            else if (el.multiple) Array.prototype.forEach.call(el.options, function (o) { o.selected = valor.indexOf(o.value) !== -1; });
            else el.value = valor;
            // Para que los campos que dependen de este (raza, horas libres...) se actualicen.
            el.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }

    function avisar(form, clave) {
        var aviso = document.createElement('div');
        aviso.className = 'alerta alerta-info aviso-borrador';
        aviso.innerHTML = '<div style="flex:1">Recuperamos lo que habías escrito antes de salir de esta página.</div>' +
                          '<button type="button" class="btn btn-suave btn-chico">Descartar</button>';
        aviso.querySelector('button').addEventListener('click', function () {
            almacen.removeItem(clave);
            location.reload();
        });
        form.insertBefore(aviso, form.firstChild);
    }

    document.querySelectorAll('form').forEach(function (form, i) {
        if ((form.method || '').toLowerCase() !== 'post') return;      // los buscadores no
        if (form.dataset.sinBorrador !== undefined || form.getAttribute('action') === '/logout/') return;
        if (!campos(form).length) return;                               // botones como "Llegó"

        var clave = PREFIJO + location.pathname + location.search + ':' + i;
        var guardado = almacen.getItem(clave);
        if (guardado) {
            try { rellenar(form, JSON.parse(guardado)); avisar(form, clave); } catch (e) { almacen.removeItem(clave); }
        }

        function guardar() {
            try { almacen.setItem(clave, JSON.stringify(leer(form))); } catch (e) { /* sin espacio: no pasa nada */ }
        }
        form.addEventListener('input', guardar);
        form.addEventListener('change', guardar);
        // Al guardar o cancelar, el borrador ya no sirve.
        form.addEventListener('submit', function () { almacen.removeItem(clave); });
        form.querySelectorAll('a').forEach(function (a) {
            a.addEventListener('click', function () { almacen.removeItem(clave); });
        });
    });

    // Al cerrar sesión se borran todos los borradores.
    var salir = document.querySelector('form[action="/logout/"]');
    if (salir) salir.addEventListener('submit', function () {
        Object.keys(almacen).forEach(function (k) { if (k.indexOf(PREFIJO) === 0) almacen.removeItem(k); });
    });
})();

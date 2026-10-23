// Nueva mascota: la lista de razas muestra solo las del tipo elegido.
(function () {
    var tipo = document.getElementById('id_especie');
    var raza = document.getElementById('id_raza');
    var datos = document.getElementById('razas-por-tipo');
    if (!tipo || !raza || !datos) return;

    // [[id de raza, id de tipo], ...] -> {id de raza: id de tipo}
    var tipoDeRaza = {};
    JSON.parse(datos.textContent).forEach(function (par) {
        tipoDeRaza[par[0]] = String(par[1]);
    });

    function filtrar() {
        Array.prototype.forEach.call(raza.options, function (opcion) {
            if (!opcion.value) return;              // "Sin raza o desconocida"
            var visible = tipo.value !== '' && tipoDeRaza[opcion.value] === tipo.value;
            opcion.hidden = !visible;
            opcion.disabled = !visible;
        });
        // Si la raza elegida no es del tipo nuevo, se limpia.
        var elegida = raza.options[raza.selectedIndex];
        if (elegida && elegida.disabled) raza.value = '';
        raza.disabled = tipo.value === '';
    }

    tipo.addEventListener('change', filtrar);
    filtrar();
})();

// El número de microchip solo se pide si la mascota tiene microchip (y es opcional).
(function () {
    var opciones = document.querySelectorAll('input[name="tiene_microchip"]');
    var numero = document.getElementById('id_microchip');
    if (!opciones.length || !numero) return;
    var campo = numero.closest('.campo');

    function mostrar() {
        var elegida = document.querySelector('input[name="tiene_microchip"]:checked');
        var tiene = elegida && elegida.value === 'True';
        campo.hidden = !tiene;
        if (!tiene) numero.value = '';
    }

    opciones.forEach(function (o) { o.addEventListener('change', mostrar); });
    mostrar();
})();

// Buscador de razas: en vez de la lista nativa (que con 48 razas ocupa toda la
// pantalla), un campo con lupa que filtra mientras se escribe y muestra una
// lista corta con desplazamiento. El <select> original sigue existiendo y es
// el que se envía, así que el formulario funciona igual sin JavaScript.
(function () {
    var select = document.getElementById('id_raza');
    if (!select) return;

    var caja = document.createElement('div');
    caja.className = 'combo';
    caja.innerHTML =
        '<div class="combo-campo">' +
        '  <svg class="icono-sm" aria-hidden="true"><use href="#i-lupa"/></svg>' +
        '  <input type="text" class="combo-input" autocomplete="off" role="combobox"' +
        '         aria-expanded="false" aria-autocomplete="list" placeholder="Buscar raza…">' +
        '  <button type="button" class="combo-limpiar" aria-label="Quitar la raza" hidden>×</button>' +
        '</div>' +
        '<ul class="combo-lista" role="listbox" hidden></ul>';
    select.insertAdjacentElement('afterend', caja);
    select.hidden = true;

    var input = caja.querySelector('.combo-input');
    var lista = caja.querySelector('.combo-lista');
    var limpiar = caja.querySelector('.combo-limpiar');
    var activa = -1;

    // Las opciones válidas son las que el filtro por tipo dejó habilitadas.
    function opciones() {
        return Array.prototype.filter.call(select.options, function (o) {
            return o.value && !o.disabled;
        });
    }

    function sinTildes(texto) {
        return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    }

    function mostrarElegida() {
        var o = select.options[select.selectedIndex];
        input.value = o && o.value ? o.text : '';
        limpiar.hidden = !select.value;
        input.disabled = select.disabled;
        input.placeholder = select.disabled ? 'Primero elige el tipo de mascota' : 'Buscar raza…';
    }

    function abrir() {
        if (select.disabled) return;
        var texto = sinTildes(input.value === (select.options[select.selectedIndex] || {}).text ? '' : input.value);
        var visibles = opciones().filter(function (o) { return sinTildes(o.text).indexOf(texto) !== -1; });
        lista.innerHTML = '';
        visibles.forEach(function (o) {
            var li = document.createElement('li');
            li.textContent = o.text;
            li.dataset.valor = o.value;
            li.setAttribute('role', 'option');
            if (o.value === select.value) li.classList.add('elegida');
            lista.appendChild(li);
        });
        if (!visibles.length) {
            var vacio = document.createElement('li');
            vacio.className = 'combo-vacio';
            vacio.textContent = 'No hay razas con ese nombre. Puedes dejarla en blanco.';
            lista.appendChild(vacio);
        }
        activa = -1;
        lista.hidden = false;
        input.setAttribute('aria-expanded', 'true');
    }

    function cerrar() {
        lista.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        mostrarElegida();
    }

    function elegir(valor) {
        select.value = valor;
        select.dispatchEvent(new Event('change'));
        cerrar();
    }

    function marcar(indice) {
        var items = lista.querySelectorAll('li[data-valor]');
        if (!items.length) return;
        activa = (indice + items.length) % items.length;
        items.forEach(function (li, i) { li.classList.toggle('activa', i === activa); });
        items[activa].scrollIntoView({ block: 'nearest' });
    }

    input.addEventListener('focus', function () { input.select(); abrir(); });
    input.addEventListener('input', abrir);
    input.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown') { e.preventDefault(); if (lista.hidden) abrir(); marcar(activa + 1); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); marcar(activa - 1); }
        else if (e.key === 'Enter') {
            var item = lista.querySelectorAll('li[data-valor]')[activa];
            if (!lista.hidden && item) { e.preventDefault(); elegir(item.dataset.valor); }
        } else if (e.key === 'Escape') { cerrar(); }
    });
    // mousedown para elegir antes de que el campo pierda el foco.
    lista.addEventListener('mousedown', function (e) {
        var li = e.target.closest('li[data-valor]');
        if (li) { e.preventDefault(); elegir(li.dataset.valor); }
    });
    input.addEventListener('blur', function () { setTimeout(cerrar, 120); });
    limpiar.addEventListener('click', function () { elegir(''); input.focus(); });

    // Cuando cambia el tipo de mascota, el filtro original ajusta el select:
    // se actualiza el texto del buscador.
    var tipo = document.getElementById('id_especie');
    if (tipo) tipo.addEventListener('change', function () { setTimeout(mostrarElegida, 0); });
    mostrarElegida();
})();

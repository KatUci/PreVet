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

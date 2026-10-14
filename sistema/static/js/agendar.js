// Agendar hora: al elegir un tipo de mascota se muestran solo las de ese tipo.
// Sin JavaScript igual funciona: se ven todas, agrupadas por tipo.
(function () {
    var filtro = document.getElementById('filtroTipo');
    if (!filtro) return;

    filtro.addEventListener('change', function (e) {
        var tipo = e.target.value;
        document.querySelectorAll('.grupo-tipo').forEach(function (grupo) {
            grupo.hidden = tipo !== '' && grupo.dataset.tipo !== tipo;
        });
    });
})();

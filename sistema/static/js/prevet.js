// Visor de imagen: cualquier <img class="ampliable"> se abre en grande.
(function () {
    var visor = document.getElementById('visor');
    var img = document.getElementById('visorImg');
    var pie = document.getElementById('visorPie');

    function abrir(origen, texto) {
        img.src = origen;
        img.alt = texto || '';
        pie.textContent = texto || '';
        visor.classList.add('abierto');
        document.body.style.overflow = 'hidden';
    }

    function cerrar() {
        visor.classList.remove('abierto');
        document.body.style.overflow = '';
        img.removeAttribute('src');
    }

    document.addEventListener('click', function (e) {
        var foto = e.target.closest('.ampliable');
        if (foto) {
            abrir(foto.currentSrc || foto.src, foto.alt);
            return;
        }
        // Cerrar con la X o tocando el fondo, no la imagen.
        if (e.target.closest('#visorCerrar') || e.target === visor) cerrar();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && visor.classList.contains('abierto')) cerrar();
    });
})();

// El modal se cierra con Escape, no solo con el botón.
document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var m = document.getElementById('modal-salir');
    if (m && m.checked) m.checked = false;
});

// Modo claro / noche. La elección queda guardada en el navegador.
function alternarTema() {
    var raiz = document.documentElement;
    var oscuro = raiz.getAttribute('data-tema') === 'oscuro';
    if (oscuro) {
        raiz.removeAttribute('data-tema');
        localStorage.setItem('tema', 'claro');
    } else {
        raiz.setAttribute('data-tema', 'oscuro');
        localStorage.setItem('tema', 'oscuro');
    }
}

['botonTema', 'botonTemaMovil'].forEach(function (id) {
    var b = document.getElementById(id);
    if (b) b.addEventListener('click', alternarTema);
});

// Un doble clic en "Confirmar" llegaba a registrar dos ventas y a
// descontar el stock dos veces. Al enviar, el botón se bloquea.
document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form.method.toLowerCase() !== 'post') return;

    var boton = form.querySelector('button[type="submit"], button:not([type])');
    if (!boton || boton.dataset.enviando) return;

    boton.dataset.enviando = '1';
    boton.dataset.textoOriginal = boton.innerHTML;
    boton.innerHTML = 'Guardando…';

    // Deshabilitar de inmediato cancelaría el envío en algunos navegadores.
    setTimeout(function () { boton.disabled = true; }, 0);

    // Si el navegador vuelve atrás con la página en caché, se restaura.
    window.addEventListener('pageshow', function () {
        boton.disabled = false;
        delete boton.dataset.enviando;
        if (boton.dataset.textoOriginal) boton.innerHTML = boton.dataset.textoOriginal;
    });
});

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

// Un doble clic en "Guardar" o "Agendar" podía enviar el formulario dos
// veces y duplicar el registro. Al enviar, el botón se bloquea.
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

// Atajo "/": lleva al buscador global, salvo que ya se esté escribiendo en un campo.
document.addEventListener('keydown', function (e) {
    var buscador = document.getElementById('buscadorGlobal');
    if (!buscador || e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    var activo = document.activeElement;
    if (activo && (activo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(activo.tagName))) return;
    e.preventDefault();
    buscador.focus();
});

// Vista previa de una foto apenas se elige, antes de guardarla. Si el campo
// indica data-vista-previa, se reemplaza esa imagen (la foto actual); si no,
// la vista previa aparece debajo del campo.
var PESO_MAXIMO_FOTO = 10 * 1024 * 1024;

document.querySelectorAll('input[type="file"][accept^="image"]').forEach(function (input) {
    input.addEventListener('change', function () {
        var campo = input.closest('.campo') || input.parentNode;
        var aviso = campo.querySelector('.aviso-foto');
        var archivo = input.files && input.files[0];
        var vista = input.dataset.vistaPrevia ? document.getElementById(input.dataset.vistaPrevia)
                                              : campo.querySelector('.vista-previa');
        if (aviso) aviso.remove();
        if (!archivo || !archivo.type.startsWith('image/')) return;

        if (archivo.size > PESO_MAXIMO_FOTO) {
            aviso = document.createElement('div');
            aviso.className = 'ayuda aviso-foto';
            aviso.textContent = 'Esta foto pesa más de 10 MB: elige una más liviana.';
            campo.appendChild(aviso);
        }

        // Si lo que hay es el ícono de la mascota (no una imagen), se cambia por una.
        if (!vista || vista.tagName !== 'IMG') {
            var img = document.createElement('img');
            img.alt = 'Vista previa de la foto';
            if (vista) {
                img.className = vista.className + ' ampliable';
                img.id = vista.id;
                vista.replaceWith(img);
            } else {
                img.className = 'vista-previa ampliable';
                input.insertAdjacentElement('afterend', img);
            }
            vista = img;
        }
        if (vista.dataset.url) URL.revokeObjectURL(vista.dataset.url);
        vista.dataset.url = URL.createObjectURL(archivo);
        vista.src = vista.dataset.url;
    });
});

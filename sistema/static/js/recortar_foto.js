// Editor de la foto de la mascota: al elegir una foto se puede arrastrar para
// moverla y usar el zoom para acercarla, con una vista previa redonda de cómo
// va a quedar. Al guardar se sube solo lo que quedó dentro del marco.
// Sin JavaScript igual funciona: se sube la foto completa.
(function () {
    var input = document.querySelector('input[type="file"][data-recortar]');
    var editor = document.getElementById('recorte');
    if (!input || !editor) return;

    var marco = document.getElementById('recorteCanvas');
    var previa = document.getElementById('recortePrevia');
    var zoom = document.getElementById('recorteZoom');
    var actual = document.getElementById('fotoActual');
    var ctx = marco.getContext('2d');
    var LADO = marco.width;                // el marco es cuadrado
    var PESO_MAXIMO = 10 * 1024 * 1024;
    var foto = null, base = 1, dx = 0, dy = 0, arrastrando = null;

    // Calcula dónde va la foto dentro de un cuadro de `lado` píxeles.
    function posicion(lado) {
        var escala = base * parseFloat(zoom.value) * (lado / LADO);
        var ancho = foto.width * escala, alto = foto.height * escala;
        // La foto siempre cubre el marco: no se puede mover tanto que quede un borde vacío.
        var maxX = (ancho - lado) / 2, maxY = (alto - lado) / 2;
        var mx = Math.max(-maxX, Math.min(maxX, dx * (lado / LADO)));
        var my = Math.max(-maxY, Math.min(maxY, dy * (lado / LADO)));
        return { x: (lado - ancho) / 2 + mx, y: (lado - alto) / 2 + my, ancho: ancho, alto: alto,
                 mx: mx / (lado / LADO), my: my / (lado / LADO) };
    }

    function dibujar() {
        var p = posicion(LADO);
        dx = p.mx; dy = p.my;               // se guarda la posición ya ajustada a los bordes
        ctx.clearRect(0, 0, LADO, LADO);
        ctx.drawImage(foto, p.x, p.y, p.ancho, p.alto);
        var pctx = previa.getContext('2d');
        pctx.clearRect(0, 0, previa.width, previa.height);
        pctx.drawImage(marco, 0, 0, previa.width, previa.height);
    }

    input.addEventListener('change', function () {
        var archivo = input.files && input.files[0];
        if (!archivo || !archivo.type.startsWith('image/')) return;
        var aviso = document.getElementById('recorteAviso');
        aviso.hidden = archivo.size <= PESO_MAXIMO;
        var img = new Image();
        img.onload = function () {
            foto = img;
            base = Math.max(LADO / img.width, LADO / img.height);   // la foto llena el marco
            zoom.value = 1; dx = 0; dy = 0;
            editor.hidden = false;
            if (actual) actual.hidden = true;
            dibujar();
        };
        img.src = URL.createObjectURL(archivo);
    });

    // Arrastrar con el mouse o con el dedo.
    marco.addEventListener('pointerdown', function (e) {
        if (!foto) return;
        arrastrando = { x: e.clientX - dx, y: e.clientY - dy };
        marco.setPointerCapture(e.pointerId);
    });
    marco.addEventListener('pointermove', function (e) {
        if (!arrastrando) return;
        dx = e.clientX - arrastrando.x;
        dy = e.clientY - arrastrando.y;
        dibujar();
    });
    marco.addEventListener('pointerup', function () { arrastrando = null; });
    zoom.addEventListener('input', function () { if (foto) dibujar(); });

    // Al guardar se reemplaza el archivo por el recorte, de 800 x 800 píxeles.
    input.form.addEventListener('submit', function (e) {
        if (!foto) return;
        e.preventDefault();
        var salida = document.createElement('canvas');
        salida.width = salida.height = 800;
        var p = posicion(800);
        salida.getContext('2d').drawImage(foto, p.x, p.y, p.ancho, p.alto);
        salida.toBlob(function (blob) {
            var datos = new DataTransfer();
            datos.items.add(new File([blob], 'foto.jpg', { type: 'image/jpeg' }));
            input.files = datos.files;
            input.form.submit();
        }, 'image/jpeg', 0.9);
    });
})();

# Estrategia de pruebas

## Capas

### Caracterización heredada

`tests/test_pack_ai.py` fija el comportamiento observable de la versión 1.x: exclusiones, detección de secretos, Git, nombres y flags combinados. Su función es impedir regresiones durante la migración modular.

### Unitarias

`tests/unit/` verifica:

- contratos inmutables y neutrales respecto de UI;
- eventos y exclusiones normalizadas;
- preservación atómica de una salida anterior;
- verificación integral del temporal antes del reemplazo y compresión DEFLATE;
- métricas derivadas de los mismos bytes escritos;
- LOC físico no vacío, detección por lenguaje y exclusión de documentación general;
- preview sin creación de ZIP;
- ranking configurable por tokens;
- inclusión de imágenes y PDF con firma válida;
- exclusión de ejecutables incluso con extensión engañosa;
- preservación de bytes en codificaciones heredadas;
- inclusión predeterminada de lockfiles textuales, grandes y binarios conocidos;
- exclusión uniforme de lockfiles mediante `include_lockfiles=False` y `--no-lockfiles`;
- fallback heurístico del tokenizador;
- creación del ZIP aunque falle completamente el análisis de métricas;
- árbol de carpetas con nodos bloqueados visibles y no recorridos;
- traducción de exclusiones y opciones entre GUI, `PackRequest` y comandos reproducibles;
- contención de los interruptores invisibles dentro de su control y anclaje permanente del root al viewport;
- reescaneo antes de generar y descarte de exclusiones que ya no existen;
- despacho de `packai gui` sin modificar el parser heredado.

Los estimadores falsos hacen que las pruebas de dominio sean deterministas y no dependan de una versión concreta de `tiktoken`.

### Contratos

`tests/contract/` protege `PackService.pack`, `PackService.preview`, `PackRequest`, `PackResult`, `PackPreview`, `PackMetrics`, `TokenEstimator` y la fachada heredada.

### Integración

Las pruebas abren ZIP reales y comparan bytes. Las fixtures que validan preservación exacta escriben bytes, no texto sujeto a traducción `LF`/`CRLF` de Windows. Git y portapapeles se aíslan porque dependen del sistema. Un smoke test con `tiktoken` instalado debe comprobar, sin acceso de red, que el método informado sea `tiktoken:o200k_base` y no degradado. También se verifica que el mismo vocabulario sea aceptado con `LF` o `CRLF`, y que una alteración distinta de los saltos de línea active el fallback.

El escáner tiene regresiones explícitas para diferenciar credenciales literales de símbolos de código que contienen palabras como `token` o `password`. El smoke test del propio repositorio debe conservar los módulos Python, los recursos JavaScript de la GUI y el vocabulario del tokenizador.

## Gate local y CI

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/packai
uv run pytest
uv run pytest --cov=packai --cov-fail-under=70
```

El umbral mínimo es 70%. No debe reducirse para ocultar una regresión.

## Regla para cambios

- Nuevo formato binario permitido: firma explícita, prueba positiva, prueba de extensión falsa y documentación de seguridad.
- Nuevo tokenizador: implementación de `TokenEstimator`, pruebas deterministas y política de fallback.
- Cambio de contrato público: ADR y prueba de contrato.
- Nuevo lenguaje para LOC: extensión o nombre inequívoco, prueba de conteo y documentación de semántica.
- Corrección de bug: reproducción mínima y prueba de regresión.
- Nueva GUI: debe consumir `preview`/`pack`; no debe duplicar clasificación, métricas ni tokenización.
- Cambio en selección jerárquica: prueba sobre exclusiones mínimas y comandos reproducibles.
- Cambio en monitor: la corrección debe seguir dependiendo del reescaneo previo a `pack`, no de la entrega perfecta de eventos.
- Nuevo lockfile reconocido: nombre o ruta convencional inequívoca, prueba de inclusión y cobertura del interruptor global.

### GUI manual

La validación visual requiere un equipo con backend gráfico:

```bash
uv sync --locked --extra gui
uv run packai gui .
```

Comprobar: estados triestado, nodos bloqueados, actualización tras crear/eliminar carpetas, Force, contexto Git, interruptor de lockfiles, copia de comandos y dos generaciones consecutivas después de modificar archivos. Para la regresión del viewport, desplazarse hasta Opciones, alternar varias veces `Incluir lockfiles` en un proyecto cuya preview cambie mucho de altura y redimensionar/maximizar la ventana; la barra superior debe permanecer en `y=0`, el dock debe seguir pegado al borde inferior y el scroll solo debe ocurrir dentro de los paneles. La CI no debe intentar abrir una ventana nativa en un runner sin escritorio.

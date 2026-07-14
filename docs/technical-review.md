# Revisión técnica

## Riesgos originales para el crecimiento

1. El recorrido, seguridad, Git, portapapeles y CLI estaban concentrados en un módulo único.
2. No existía un contrato que una GUI pudiera consumir sin capturar `stdout`.
3. La salida no era atómica.
4. Las dependencias externas no eran sustituibles.
5. No había contratos explícitos de métricas ni una fuente de verdad compartida con el ZIP.

## Arquitectura vigente

- `PackService` expone `pack` y `preview`.
- `PackRequest`, `PackPreview`, `PackResult` y `PackMetrics` son contratos inmutables.
- `GitContextProvider` y `TokenEstimator` son puertos sustituibles.
- `ArchiveService` construye un `ArchivePlan` con los bytes exactos que se analizarán y escribirán.
- El ZIP usa temporal y reemplazo atómico.
- `pack_ai.py` conserva la superficie 1.x.

## Mejora de métricas

La versión 2.1 añade:

- archivos incluidos, textuales y binarios;
- tamaño exacto sin comprimir;
- tamaño físico del ZIP después de crearlo;
- tokens estimados sobre contenido textual;
- ranking configurable mediante `token_top` y `--token-top`;
- preview sin compresión;
- `tiktoken:o200k_base` como método principal con vocabulario local verificado;
- inicialización exacta sin red ni caché previa;
- fallback degradado por bytes UTF-8;
- imágenes raster y PDF permitidos por firma, sin aporte de tokens;
- exclusión explícita de ejecutables y binarios desconocidos.

## Contratos que futuras actualizaciones deben respetar

1. `PackService.pack` y `PackService.preview` no imprimen ni dependen de framework.
2. Una misma operación calcula y comprime los mismos bytes.
3. La tokenización no modifica el contenido archivado.
4. `PackResult.metrics` puede ser `None` si el análisis completo falla; el ZIP sigue siendo válido.
5. `PackPreview.metrics.zip_size` es `None` porque no se realizó compresión.
6. Los binarios permitidos aportan cantidad y tamaño, pero no tokens.
7. Ejecutables y binarios desconocidos no se incluyen ni con `force`.
8. `.env` y variantes reales permanecen como exclusión estricta.
9. Los lockfiles conocidos se incluyen por defecto y una única opción compartida por CLI, GUI y API puede excluirlos.
10. Los hallazgos contienen valores enmascarados.
11. La salida anterior se conserva ante fallos previos a `os.replace`.

## Riesgos residuales

- El plan conserva temporalmente todo el contenido incluido en memoria. El supuesto operativo actual es un proyecto inferior a 100 MB.
- PDF e imágenes se validan por firma, pero no se inspecciona su contenido interno para secretos.
- El conteo es exacto para `o200k_base`, pero sigue siendo una estimación del costo de un modelo concreto porque cada modelo puede aplicar otro encoding o envolver el contenido con tokens adicionales.
- El fallback heurístico es deliberadamente aproximado y se marca como degradado.
- La detección de secretos continúa basada en expresiones regulares.
- Una preview puede quedar obsoleta si los archivos cambian antes del pack; el pack siempre genera su propia instantánea actual.

## Verificación histórica de la iteración 2.1

- Ruff format/check: correcto.
- mypy estricto: correcto en 16 módulos.
- Pytest: 59 pruebas aprobadas.
- Cobertura: 75.54%, con gate mínimo de 70%.
- Smoke test: texto, PNG y PDF incluidos; ejecutable excluido; tamaños del reporte coinciden con el ZIP.
- El vocabulario local `o200k_base` fue validado mediante SHA-256 y el smoke test exacto devolvió `degraded=False` sin acceso de red.
- `uv.lock` no forma parte del artefacto entregado.

## Mejora de interfaz gráfica

La versión 2.2 introdujo una superficie PyWebView opcional sin desplazar al CLI. La versión 2.3 añade tamaños recursivos al árbol:

- `packai gui .` con los mismos flags iniciales relevantes;
- árbol exclusivo de carpetas con estados marcado, desmarcado, indeterminado y bloqueado;
- carpetas ignoradas visibles como hojas deshabilitadas;
- tamaño recursivo por carpeta obtenido durante el mismo recorrido del árbol;
- `node_modules` y otros subárboles bloqueados se representan sin atravesarlos ni calcular su peso;
- selección efímera traducida a exclusiones relativas mínimas;
- preview reactiva de tokens, tamaños, archivos y hallazgos;
- generación repetible que reescanea antes de escribir;
- monitor de watchdog con debounce y sondeo de baja frecuencia como fallback;
- comandos reproducibles para pack directo y reapertura de la GUI;
- React 18.3.1 vendorizado con licencia y hashes, sin CDN ni servidor local;
- diagnóstico accionable para dependencias opcionales, WebView2 y backends Linux/macOS.

La GUI no persiste configuración, no elige una ruta de salida y no contiene reglas de dominio propias. `GuiBridge` traduce datos serializables y delega en `PackService`.

## Riesgos residuales de la GUI

- La entrega visual final depende del motor nativo de cada sistema operativo; debe validarse en Windows con WebView2.
- Watchdog puede producir ráfagas de eventos en repositorios activos. El debounce reduce previews repetidas y la corrección no depende del watcher.
- Una preview en curso no se cancela a mitad del análisis; respuestas obsoletas se descartan en React. El supuesto de proyectos menores a 100 MB mantiene acotado el costo.
- Reincorporar una rama bajo un ancestro excluido puede expandirse a varias exclusiones hermanas porque el contrato del CLI solo expresa carpetas excluidas.
- React se distribuye como recurso estático y requiere una actualización consciente de versión, licencia y hashes.

## Verificación de la entrega 2.3

- Ruff format/check: correcto en el proyecto completo.
- mypy estricto: sin errores en 25 módulos de `src/packai`.
- Pytest: 79 pruebas aprobadas.
- Cobertura: 79.02%, con gate mínimo de 70%.
- Tokenizador: vocabulario `o200k_base` local, 199,998 entradas y SHA-256 verificado.
- Wheel: construido desde una copia aislada y revisado para comprobar recursos de GUI y tokenización.
- Recursos: HTML, CSS, JavaScript, React, licencias y vocabulario presentes dentro del wheel.
- CLI: versión, parser heredado y ayuda de `packai gui` comprobados.
- No se abrió una ventana nativa en este entorno Linux sin escritorio.
- `uv.lock` no se incluye en el artefacto entregado.


## Iteración 2.4: LOC y ZIP verificado

- `PackMetrics` añade `code_files`, `code_lines` y `language_code_lines` con valores predeterminados para mantener compatibilidad con construcciones existentes.
- El conteo usa líneas físicas no vacías y agrupa lenguajes por extensión, nombre convencional o shebang.
- CLI y GUI muestran total de LOC, archivos de código y desglose por lenguaje; la API entrega la misma estructura serializable.
- El escritor usa DEFLATE nivel 9, ZIP64 y verificación completa del temporal antes de `os.replace`.
- Las pruebas de regresión cubren CRLF, líneas vacías, comentarios, varios lenguajes, archivos no fuente, compresión, CRC y preservación atómica ante fallo de verificación.

## Verificación de la entrega 2.4

- Ruff format/check: correcto en el proyecto completo.
- mypy estricto: sin errores en 25 módulos de `src/packai`.
- Pytest: 84 pruebas aprobadas.
- Cobertura: 79.68%, con gate mínimo de 70%.
- Sintaxis de `app.js`: validada con `node --check`.
- Wheel y sdist 2.4.0: construidos correctamente y revisados durante el build.
- Métrica del propio proyecto bajo su política normal: 35 archivos de código y 2,265 líneas físicas no vacías.


## Política de lockfiles

- La lista de nombres reconocidos está centralizada en `packai.policy`; no se usa un patrón genérico `*.lock` que pueda capturar archivos ajenos a gestores de dependencias.
- `PackRequest.include_lockfiles` vale `True` por defecto y se propaga sin duplicar reglas a `ArchiveService`.
- CLI y GUI exponen `--lockfiles` / `--no-lockfiles`; la GUI añade un interruptor y genera comandos reproducibles con `--no-lockfiles` cuando corresponde.
- La decisión específica de lockfiles prevalece sobre patrones antiguos de `.ignore2packai`, evitando que configuraciones heredadas hagan que el interruptor parezca no funcionar.
- Los lockfiles textuales mantienen el escaneo de secretos. Los lockfiles binarios reconocidos se permiten sin relajar la política para otros binarios desconocidos.
- El nuevo campo se añadió al final de `PackRequest` para no desplazar los argumentos posicionales existentes.

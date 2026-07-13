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
- `tiktoken:o200k_base` como método principal;
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
9. Los hallazgos contienen valores enmascarados.
10. La salida anterior se conserva ante fallos previos a `os.replace`.

## Riesgos residuales

- El plan conserva temporalmente todo el contenido incluido en memoria. El supuesto operativo actual es un proyecto inferior a 100 MB.
- PDF e imágenes se validan por firma, pero no se inspecciona su contenido interno para secretos.
- El conteo es exacto para `o200k_base`, pero sigue siendo una estimación del costo de un modelo concreto porque cada modelo puede aplicar otro encoding o envolver el contenido con tokens adicionales.
- El fallback heurístico es deliberadamente aproximado y se marca como degradado.
- La detección de secretos continúa basada en expresiones regulares.
- Una preview puede quedar obsoleta si los archivos cambian antes del pack; el pack siempre genera su propia instantánea actual.

## Verificación de esta entrega

- Ruff format/check: correcto.
- mypy estricto: correcto en 16 módulos.
- Pytest: 59 pruebas aprobadas.
- Cobertura: 75.54%, con gate mínimo de 70%.
- Smoke test: texto, PNG y PDF incluidos; ejecutable excluido; tamaños del reporte coinciden con el ZIP.
- El entorno aislado no tenía `tiktoken` instalado, por lo que el smoke test ejercitó el fallback. El adapter principal queda cubierto por contrato e import dinámico y debe verificarse tras actualizar el lockfile propio.
- `uv.lock` no fue creado, modificado ni incluido.

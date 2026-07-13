# Revisión técnica

## Diagnóstico del estado recibido

### Bloqueantes para crecimiento

1. **Módulo único de más de 700 líneas.** El recorrido de archivos, reglas de seguridad, Git, portapapeles, CLI y presentación compartían estado global y llamadas directas.
2. **Ausencia de contrato de aplicación.** Una GUI habría tenido que llamar funciones de bajo nivel, capturar `stdout` y reconstruir reglas de exclusión.
3. **Salida no atómica.** El ZIP de destino se abría directamente; un fallo durante el recorrido podía dejar una salida parcial o reemplazar una anterior válida.
4. **Empaquetado Python incompleto.** No existía paquete `src/`, entry point instalable ni build backend declarado.
5. **Tipos inconsistentes.** `FileFinding` no declaraba el campo `forced` que sí se producía y consumía en ejecución.
6. **Dependencias externas rígidas.** Git y portapapeles se invocaban desde la misma capa que las reglas de negocio.
7. **Gate incompleto.** Había pruebas de regresión útiles, pero no lint, tipado, cobertura, CI ni pruebas explícitas de contrato.
8. **Decisiones no documentadas.** Las invariantes de seguridad y compatibilidad estaban dispersas entre código, README y tests.

## Solución aplicada

- Se creó `src/packai` con límites de módulo explícitos.
- `PackRequest`, `PackResult`, hallazgos y eventos son dataclasses inmutables.
- `PackService` es la API recomendada para CLI, GUI y futuras integraciones.
- `GitContextProvider` permite sustituir Git por un fake o un adaptador alternativo.
- `ArchiveService` escribe en temporal y usa reemplazo atómico.
- `pack_ai.py` conserva la superficie 1.x y adapta contratos nuevos a diccionarios heredados.
- Se agregó entry point `packai`, layout `src`, `.python-version`, build backend y lockfile actualizado.
- Se separaron pruebas unitarias, de contrato y caracterización.
- Se configuraron Ruff, mypy estricto, cobertura mínima y CI para Python 3.12/3.13.
- Se documentaron arquitectura, dominio, estrategia de pruebas y ADR.

## Contratos que futuras actualizaciones deben respetar

1. `PackService.pack(PackRequest, reporter) -> PackResult` no imprime ni depende de framework.
2. Los eventos de progreso se agregan de forma compatible; no se cambia el significado de eventos existentes sin versión mayor.
3. Los errores esperados heredan de `PackAIError`.
4. `.env` y variantes reales permanecen como exclusión estricta.
5. Los hallazgos exponen valores enmascarados, nunca secretos completos.
6. La salida anterior se conserva ante fallo antes de `os.replace`.
7. La fachada `pack_ai.py` permanece cubierta por pruebas hasta una retirada documentada.
8. Todo comportamiento nuevo incluye prueba en la capa mínima adecuada.

## Riesgos residuales

- La detección de secretos sigue siendo heurística y basada en regex; requiere revisión manual y evolución de patrones.
- El portapapeles continúa siendo un adaptador orientado a PowerShell. Una GUI multiplataforma debe proporcionar su propia integración.
- El recorrido y escaneo son secuenciales. Antes de paralelizar se debe medir y preservar orden determinista, cancelación y atomicidad.
- Los archivos mayores de 1 MiB se tratan como hallazgo no escaneable. Si se cambia esa política, debe existir límite configurable y pruebas de memoria/rendimiento.
- `.ignore2packai` usa semántica `fnmatch`, no semántica completa de `.gitignore`; cambiarlo sería un cambio de comportamiento que exige migración.

## Siguiente evolución recomendada

La primera GUI debería ser un adaptador delgado: selección de raíz/salida, edición de `PackRequest`, render de `ProgressEvent`, cancelación cooperativa y presentación de `PackResult`. No debe duplicar escaneo, exclusiones ni generación Git.

## Verificación de esta entrega

La corrección de portabilidad se verificó con Python 3.13.5:

- `pytest`: 51 pruebas aprobadas.
- `pytest --cov=packai --cov-fail-under=70`: 74.21% de cobertura.
- La regresión simula el `NotADirectoryError` observado en Windows y exige que los adaptadores Git lo traduzcan a ausencia de contexto, sin propagar la excepción.
- El `uv.lock` del usuario no fue modificado y no forma parte del ZIP de entrega.

Los controles `ruff` y `mypy` permanecían correctos en la ejecución de Windows aportada antes de esta corrección.

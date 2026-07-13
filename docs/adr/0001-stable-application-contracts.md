# ADR 0001: contratos estables y núcleo independiente de interfaz

## Estado

Aceptado.

## Contexto

La implementación original concentraba CLI, recorrido de archivos, detección de secretos, Git, portapapeles y presentación en un único módulo. Una futura GUI habría tenido que invocar funciones acopladas a `print`, reconstruir reglas de exclusión o monkeypatchar dependencias globales.

## Decisión

Se adopta un paquete `src/packai` con:

- `PackRequest` y `PackResult` inmutables como frontera del caso de uso;
- `ProgressEvent` como mecanismo neutral de progreso;
- `GitContextProvider` como puerto sustituible;
- `PackService` como fachada de aplicación;
- `ArchiveService` con reemplazo atómico;
- adaptadores separados para CLI, Git y portapapeles;
- `pack_ai.py` como fachada de compatibilidad temporal.

## Consecuencias positivas

- Una GUI puede reutilizar el mismo caso de uso sin capturar stdout.
- Los dobles de prueba implementan un protocolo pequeño.
- Las reglas de dominio quedan localizadas.
- Los cambios incompatibles pueden detectarse con pruebas de contrato.
- Un fallo no deja un ZIP parcial ni destruye la salida anterior.

## Consecuencias negativas

- Durante la transición existen dos superficies importables.
- La fachada heredada requiere pruebas hasta su retiro.
- Agregar nuevos campos a contratos públicos exige considerar compatibilidad.

## Alternativas consideradas

- Mantener el módulo único y agregar clases de GUI: rechazado por ampliar el acoplamiento.
- Reescribir y eliminar la API 1.x: rechazado porque rompería usuarios sin migración.
- Usar un framework de eventos: rechazado; una función callback tipada cubre la necesidad actual con menor carga.

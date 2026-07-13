# Arquitectura

## Objetivo

Permitir que empaquetado, previsualización y métricas evolucionen sin acoplarse al CLI y sin obligar a una futura GUI a interpretar texto impreso o monkeypatchar funciones internas.

## Dependencias

```text
CLI / PyWebView GUI / API
      |
      v
PackService (pack / preview)
      |
      v
ArchiveService -----> GitContextProvider (puerto)
      |             -> TokenEstimator (puerto)
      v
ArchivePlan -> ArchiveMetricsAnalyzer -> ZIP writer
      |
      v
content / policy / contracts / errors

Adaptadores concretos:
- subprocess Git
- tiktoken o fallback heurístico
- PowerShell clipboard
- argparse + console reporter
- PyWebView bridge + React local + watchdog
```

La dirección de dependencia apunta hacia contratos y políticas. El núcleo no importa `argparse`, PowerShell ni objetos de una GUI.

## Módulos

| Módulo | Responsabilidad |
|---|---|
| `contracts.py` | Peticiones, previews, resultados, métricas, eventos y protocolos públicos. |
| `application.py` | Valida la petición y compone la política de exclusión. |
| `archive.py` | Construye la instantánea, calcula métricas y escribe el ZIP atómicamente. |
| `content.py` | Clasifica texto, activos binarios permitidos y firmas ejecutables sin modificar bytes. |
| `metrics.py` | Agrega tamaños, conteos, tokens y ranking desde el plan exacto. |
| `tokenization.py` | Adaptador `tiktoken` offline, verificación del vocabulario y fallback heurístico degradado. |
| `policy.py` | Reglas puras de rutas, nombres sensibles y secretos. |
| `git.py` | Puerto y adaptador de Git; genera contexto de `HEAD`. |
| `clipboard.py` | Integración PowerShell aislada. |
| `cli.py` | Parseo, presentación, despacho de `gui` y traducción de errores a códigos de salida. |
| `gui/api.py` | Puente serializable que traduce estado visual a `PackRequest`. |
| `gui/tree.py` | Árbol de carpetas y estados bloqueados por política. |
| `gui/watcher.py` | Monitor de eventos con debounce y fallback de sondeo. |
| `gui/launcher.py` | Arranque opcional de PyWebView y diagnóstico del backend gráfico. |
| `gui/resources/` | React, HTML, CSS y JavaScript locales sin servidor ni CDN. |
| `pack_ai.py` | Fachada temporal de compatibilidad con 1.x. |

## Instantánea y fuente de verdad

`ArchivePlan` conserva en memoria los bytes exactos seleccionados. La clasificación y el conteo pueden decodificar una vista textual, pero el writer recibe siempre los bytes originales. Esto impide que una codificación, un BOM o caracteres heredados sean alterados por el análisis.

`PackService.preview` devuelve `PackPreview` con `zip_size=None` y no crea archivos. `PackService.pack` calcula sobre otra instantánea actual y, después del reemplazo atómico, añade el tamaño físico del ZIP a `PackMetrics`.

## Contratos de extensión

Una interfaz nueva debe:

1. Construir `PackRequest`, incluido `token_top`.
2. Invocar `PackService.preview` para una previsualización sin compresión.
3. Invocar `PackService.pack` para crear el artefacto final.
4. Renderizar `ProgressEvent`, `PackMetrics` y errores sin asumir mensajes del CLI.
5. Sustituir `GitContextProvider` o `TokenEstimator` mediante inyección cuando corresponda.

No debe importar `ConsoleReporter`, `argparse` ni funciones privadas de `archive.py`.

## Política binaria

El tokenizador exacto carga `packai.data/o200k_base.tiktoken` desde los recursos instalados y comprueba su SHA-256 antes de construir el encoder. No consulta red.

Solo se admiten por defecto imágenes raster reconocidas y PDF con firma válida. Estos miembros cuentan como binarios, aportan tamaño y no aportan tokens. Ejecutables, binarios desconocidos, multimedia y formatos de compilación siguen excluidos. `.ignore2packai`, `extra_ignore_patterns` y las exclusiones CLI pueden retirar cualquier activo permitido.

## Compatibilidad

La fachada `pack_ai.py` conserva las funciones usadas por pruebas y usuarios existentes. `PackResult.metrics` tiene valor predeterminado `None`, por lo que construcciones heredadas siguen siendo válidas. Las nuevas capacidades se incorporan al paquete `packai`.

## Consistencia de salida

El ZIP se crea en un temporal ubicado en el mismo sistema de archivos que el destino. `os.replace` ocurre después del cierre exitoso. Un fallo de tokenización degrada la estimación; un fallo total de métricas emite advertencia, pero ninguno elimina un ZIP válido.

## Flujo de la GUI

1. `packai gui` valida la raíz y traduce flags a `GuiLaunchOptions`.
2. `GuiBridge.initialize` escanea el árbol de carpetas y solicita `PackService.preview`.
3. React conserva en memoria exclusiones, opciones y estado de expansión.
4. Cada cambio de selección se agrupa con debounce y solicita una preview nueva.
5. `DirectoryChangeMonitor` invalida la caché ante cambios y solicita un refresco.
6. El botón de generación llama a `PackService.pack`, que vuelve a leer el proyecto y escribe el ZIP atómicamente.
7. La GUI renderiza `PackMetrics`, hallazgos y el comando reproducible; no interpreta salida de consola.

La caché de preview está ligada a una revisión del sistema de archivos y a las opciones que afectan el contenido. `copy_mode` no invalida métricas. La caché nunca se usa como fuente para escribir el ZIP.

## Selección jerárquica

El estado visual se deriva de exclusiones relativas:

- marcado: ningún descendiente seleccionable está excluido;
- desmarcado: el nodo o un ancestro está excluido;
- indeterminado: existe una combinación de descendientes incluidos y excluidos;
- deshabilitado: la política impide seleccionar el nodo.

Cuando se reincorpora un descendiente bajo un ancestro excluido, la interfaz sustituye la exclusión del ancestro por exclusiones de ramas hermanas. El resultado se normaliza al conjunto mínimo que puede reproducir el CLI actual.

## Dependencias gráficas opcionales

El módulo CLI importa `packai.gui.launcher` solo después de reconocer el subcomando `gui`. Por ello, la ausencia de PyWebView o watchdog no afecta imports, tests ni uso tradicional. React se distribuye como recurso estático versionado; no existe acceso de red en tiempo de ejecución.

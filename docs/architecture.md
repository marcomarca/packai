# Arquitectura

## Objetivo

Permitir que el comportamiento de empaquetado evolucione sin acoplarse al CLI actual y sin obligar a una futura GUI a interpretar texto impreso o monkeypatchar funciones internas.

## Dependencias

```text
CLI / GUI / API
      |
      v
PackService (caso de uso)
      |
      v
ArchiveService -----> GitContextProvider (puerto)
      |
      v
policy / contracts / errors

Adaptadores concretos:
- subprocess Git
- PowerShell clipboard
- argparse + console reporter
```

La dirección de dependencia apunta hacia contratos y políticas. `contracts.py`, `policy.py` y `errors.py` no importan `argparse`, PowerShell ni objetos de una GUI.

## Módulos

| Módulo | Responsabilidad |
|---|---|
| `contracts.py` | Entradas, resultados, hallazgos, eventos y protocolos públicos. |
| `application.py` | Valida la petición y compone la política de exclusión. |
| `archive.py` | Recorre, escanea y escribe el ZIP de forma atómica. |
| `policy.py` | Reglas puras de rutas, nombres sensibles y secretos. |
| `git.py` | Puerto y adaptador de Git; genera contexto de `HEAD`. |
| `clipboard.py` | Integración PowerShell aislada. |
| `cli.py` | Parseo, presentación y traducción de errores a códigos de salida. |
| `pack_ai.py` | Fachada temporal de compatibilidad con 1.x. |

## Contratos de extensión

Una interfaz nueva debe:

1. Construir `PackRequest`.
2. Invocar `PackService.pack`.
3. Renderizar `ProgressEvent` sin asumir mensajes impresos.
4. Traducir `PackAIError` a mensajes o estados propios.
5. Sustituir `GitContextProvider` mediante inyección cuando necesite sandbox, Git remoto o pruebas.

No debe importar `ConsoleReporter`, `argparse` ni funciones privadas de `archive.py`.

## Compatibilidad

La fachada `pack_ai.py` conserva las funciones usadas por las pruebas y usuarios existentes. Las nuevas capacidades se incorporan al paquete `packai`. La fachada puede eliminarse solo en una versión mayor posterior y después de documentar migración.

## Consistencia de salida

El ZIP se crea en un temporal ubicado en el mismo sistema de archivos que el destino. `os.replace` ocurre después del cierre exitoso. Esto evita salidas parciales y conserva un archivo anterior ante errores durante lectura, compresión o escritura.

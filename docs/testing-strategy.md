# Estrategia de pruebas

## Capas

### Caracterización heredada

`tests/test_pack_ai.py` fija el comportamiento observable de la versión 1.x: exclusiones, detección de secretos, Git, nombres y flags combinados. Su función es impedir regresiones durante la migración modular.

### Unitarias

`tests/unit/` verifica:

- contratos inmutables y neutrales respecto de UI;
- eventos y exclusiones normalizadas;
- preservación atómica de una salida anterior;
- métricas derivadas de los mismos bytes escritos;
- preview sin creación de ZIP;
- ranking configurable por tokens;
- inclusión de imágenes y PDF con firma válida;
- exclusión de ejecutables incluso con extensión engañosa;
- preservación de bytes en codificaciones heredadas;
- fallback heurístico del tokenizador;
- creación del ZIP aunque falle completamente el análisis de métricas.

Los estimadores falsos hacen que las pruebas de dominio sean deterministas y no dependan de una versión concreta de `tiktoken`.

### Contratos

`tests/contract/` protege `PackService.pack`, `PackService.preview`, `PackRequest`, `PackResult`, `PackPreview`, `PackMetrics`, `TokenEstimator` y la fachada heredada.

### Integración

Las pruebas abren ZIP reales y comparan bytes. Git y portapapeles se aíslan porque dependen del sistema. Un smoke test con `tiktoken` instalado debe comprobar que el método informado sea `tiktoken:o200k_base` y no degradado.

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
- Corrección de bug: reproducción mínima y prueba de regresión.
- Nueva GUI: debe consumir `preview`/`pack`; no debe duplicar clasificación, métricas ni tokenización.

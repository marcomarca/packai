# Estrategia de pruebas

## Capas

### Caracterización heredada

`tests/test_pack_ai.py` fija el comportamiento observable de la versión 1.x: exclusiones, detección de secretos, Git, nombres y flags combinados. Su función es impedir regresiones durante la migración modular.

### Unitarias

`tests/unit/` prueba el caso de uso y los servicios sin depender de consola ni Git real. Incluye:

- resultado inmutable y neutral respecto de UI;
- eventos de progreso;
- normalización de exclusiones;
- proveedor Git inyectado;
- preservación atómica de una salida anterior;
- errores de validación.

### Contratos

`tests/contract/` protege la superficie importable nueva y la fachada heredada. Un cambio incompatible requiere una decisión explícita de versión mayor y una guía de migración.

### Integración

Las pruebas que abren el ZIP verifican serialización real con `zipfile`. Git y portapapeles se aíslan porque dependen del entorno del sistema.

## Gate local y CI

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/packai
uv run pytest
uv run pytest --cov=packai --cov-fail-under=70
```

El umbral inicial es 70%. Debe subir al agregar comportamiento nuevo; no debe reducirse para ocultar una regresión.

## Regla para cambios

- Cambio de regla: prueba unitaria o parametrizada en `policy`.
- Nuevo adaptador: prueba de contrato con un fake y prueba de integración del adaptador cuando el entorno lo permita.
- Corrección de bug: reproducción mínima antes del arreglo y prueba de regresión posterior.
- Cambio de contrato público: ADR, versión mayor y prueba de migración/compatibilidad.
- Nueva GUI: sus pruebas no deben sustituir las pruebas del núcleo.

# 📦 Pack AI

**Pack AI** es una herramienta de línea de comandos diseñada para empaquetar proyectos en un archivo ZIP optimizado para su revisión por Inteligencia Artificial (ChatGPT, Gemini, Claude, etc.), asegurando la exclusión de archivos pesados y reduciendo el riesgo de filtrar secretos.

## ✨ Características principales

- **🚀 Comando Global**: Instalación sencilla para usar `packai` desde cualquier carpeta.
- **🛡️ Auditoría de Secretos**: Escaneo proactivo de claves API, tokens y credenciales con reportes detallados (tipo y número de línea).
- **🌳 Visualización Estructurada**: Muestra un árbol real del contenido que se está empaquetando.
- **📋 Copiado Automático**: Copia el archivo ZIP resultante directamente al portapapeles (en Windows).
- **⚙️ Configuración Flexible**: Soporte para archivos `.aiignore` (exclusión total) y `.aipass` (inclusión sin escaneo).
- **📄 Manejo Inteligente de Entornos**: Permite incluir archivos `.env.example` de forma segura (siempre que no contengan secretos reales).
- **🏷️ Versionado Automático**: El nombre del ZIP incluye el último commit de Git y su hash para facilitar el seguimiento de versiones.

## 📋 Requisitos

Para usar esta herramienta necesitas:

- **Windows 10/11** y **PowerShell**.
- **Python 3.12+**.
- **[uv](https://astral.sh/uv/)** instalado y disponible en el PATH.
- **Git** (opcional, para el nombrado automático basado en commits).

Para instalar `packai` como un comando global en tu sistema:

1. Clona este repositorio.
2. Abre una terminal en la carpeta del proyecto.
3. Ejecuta el instalador automático:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
4. **Reinicia tu terminal**. ¡Listo! Ahora puedes usar `packai` en cualquier sitio.

### Desinstalación
Si deseas eliminar el rastro de la herramienta y el comando global:
```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## 🛠️ Uso

```bash
# Empaquetar la carpeta actual
packai

# Empaquetar una ruta específica
packai C:\Ruta\De\Mi\Proyecto

# El orden de las opciones es flexible
packai --copy path --output mi_respaldo.zip .
packai . --copy path --output mi_respaldo.zip
```

### Opciones disponibles

| Opción | Valores | Descripción |
|---|---|---|
| `--version`, `-v` | | Muestra la versión actual del script. |
| `--copy` | `file`, `path`, `none` | Qué se copia al portapapeles (por defecto: `file`). |
| `--output` | `[ruta]` | Ruta del ZIP generado. Por defecto se nombra como `[Proyecto]-[Commit]-[Hash].zip`. |
| `--force`, `-f` | (flag) | Forzar la inclusión de archivos con alertas de seguridad (falsos positivos), **excepto archivos .env y variantes** que siempre se excluyen. |
| `-g` | (flag) | Incluye `AI_GIT_CONTEXT.md` con el diff del último commit confirmado. |
| `--no-env-example` | (flag) | Si se activa, excluye archivos `.env.example` y similares. |

### Incluir contexto del último commit

```bash
packai . -g
```

Incluye dentro del ZIP un archivo `AI_GIT_CONTEXT.md` con metadatos, archivos cambiados, estadísticas y diff del último commit confirmado (`HEAD`).

```bash
packai . -gf
```

Combina `-g` con `-f`. Incluye el contexto Git y activa el modo force para inclusiones permitidas.

El contexto Git no incluye cambios sin commit.

Los archivos `.env`, `.env.*`, `**/.env` y `**/.env.*` nunca se incluyen, ni en el ZIP normal ni dentro de `AI_GIT_CONTEXT.md`, incluso usando `-f`.

## ⚙️ Configuración Personalizada

- **`.aiignore`**: Permite definir patrones de exclusión simples (tipo `fnmatch`). Lo que coincida no entrará en el ZIP.
- **`.aipass`**: Permite incluir archivos que normalmente serían escaneados para saltarse el detector de secretos (útil para falsos positivos). **Nota importante**: No anula las exclusiones globales de seguridad (como `.git`, `node_modules`, carpetas ocultas tipo `.tmp/` o `.uv-python/`, `.env`, etc.); esos archivos siempre se ignorarán. Se mostrará una advertencia `⚠️` por seguridad.
- **`config_pack_ai.py`**: Archivo central para cambiar comportamientos por defecto del script.

## 🛡️ Seguridad y Limitaciones

**Pack AI** reduce el riesgo, pero **no garantiza una detección del 100%**. 

- El escaneo se basa en patrones Regex. No detecta secretos en formatos desconocidos.
- Siempre revisa el reporte de "Excluidos" al finalizar el empaquetado.
- Los archivos binarios, carpetas comunes (`node_modules`, `.git`, etc.) y carpetas ocultas genéricas (`.tmp/`, `.uv-python/`, etc.) se ignoran por defecto para mantener el ZIP ligero. Esta regla aplica a carpetas, no a archivos con punto en el nombre.

---
Desarrollado para optimizar el flujo de trabajo con IAs de código.


[] tiene que optimizarse para que acepte ignorar rutas de folders de un proyecto especifico facilmente desde el cli
# packai

# 📦 Pack AI

**Pack AI** es una herramienta de línea de comandos diseñada para empaquetar proyectos en un archivo ZIP optimizado para su revisión por Inteligencia Artificial (ChatGPT, Gemini, Claude, etc.), asegurando la exclusión de archivos pesados y reduciendo el riesgo de filtrar secretos.

## ✨ Características principales

- **🚀 Comando Global**: Instalación sencilla para usar `packai` desde cualquier carpeta.
- **🛡️ Auditoría de Secretos**: Escaneo proactivo de claves API, tokens y credenciales con reportes detallados (tipo y número de línea).
- **🌳 Visualización Estructurada**: Muestra un árbol real del contenido que se está empaquetando.
- **📋 Copiado Automático**: Copia el archivo ZIP resultante directamente al portapapeles (en Windows).
- **⚙️ Configuración Flexible**: Soporte para archivos `.aiignore` (exclusión total) y `.aipass` (inclusión sin escaneo).
- **📄 Manejo Inteligente de Entornos**: Permite incluir archivos `.env.example`, `.env.sample` y `.env.template` de forma segura (siempre que no contengan secretos reales).
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

# Copiar únicamente el contexto/diff del último commit al portapapeles
packai . -c

# Excluir una carpeta relativa al proyecto y todos sus hijos
packai . -e "datos"

# Excluir varias carpetas en caliente
packai . -e "datos" -e "cache/tmp"
```

### Opciones disponibles

| Opción | Valores | Descripción |
|---|---|---|
| `--version`, `-v` | | Muestra la versión actual del script. |
| `--copy` | `file`, `path`, `none` | Qué se copia al portapapeles (por defecto: `file`). |
| `--output` | `[ruta]` | Ruta del ZIP generado. Por defecto se nombra como `[Proyecto]-[Commit]-[Hash].zip`. |
| `--force`, `-f` | (flag) | Forzar la inclusión de archivos con alertas de seguridad (falsos positivos), **excepto archivos .env y variantes** que siempre se excluyen. |
| `--exclude`, `--exclude-path`, `-e`, `-E`, `-I` | `REL_DIR` | Excluye una carpeta relativa a la carpeta principal procesada y todos sus hijos. Se puede repetir. No acepta rutas absolutas ni rutas con `..`. |
| `--commit-clipboard`, `-c` | (flag) | Copia al portapapeles el Markdown de `git--diff_last_commit.md` para el último commit confirmado, sin crear ZIP. |
| `-g` | (flag) | Incluye `git--diff_last_commit.md` con el diff del último commit confirmado. |
| `--no-env-example` | (flag) | Si se activa, excluye archivos `.env.example` y similares. |

### Excluir carpetas desde CLI

```bash
packai . -e "datos"
packai . -e "datos" -e "cache/tmp"
packai C:\Ruta\De\Mi\Proyecto -e "datos"
```

La ruta de `-e` siempre se interpreta relativa a la carpeta principal que se está empaquetando. Por ejemplo, si ejecutas `packai . -e "datos"` desde la raíz de `miproyecto`, se excluye `miproyecto/datos/` y todo su contenido. No se excluye automáticamente otro directorio llamado `datos` en otra ubicación, como `src/datos/`.

La herramienta valida que la ruta no sea absoluta, no use `..`, exista dentro del proyecto y sea una carpeta. Si usas `-g` o `-c`, la misma exclusión se aplica también al contexto Git generado.

### Copiar solo el contexto del último commit

```bash
packai . -c
```

Genera el mismo contenido Markdown de `git--diff_last_commit.md`, pero no crea ZIP: solo copia ese Markdown al portapapeles.

```bash
packai . -cf
```

Combina `-c` con `-f`. Si el detector marca posibles secretos en el contexto Git, fuerza el copiado al portapapeles. Los archivos `.env` y variantes reales siguen excluidos del diff generado.

### Incluir contexto del último commit en el ZIP

```bash
packai . -g
```

Incluye dentro del ZIP un archivo `git--diff_last_commit.md` con metadatos, archivos cambiados, estadísticas y diff del último commit confirmado (`HEAD`).

```bash
packai . -gf
```

Combina `-g` con `-f`. Incluye el contexto Git y activa el modo force para inclusiones permitidas.

El contexto Git no incluye cambios sin commit.

Los archivos `.env`, `.env.local`, `.env.production` y variantes reales nunca se incluyen, ni en el ZIP normal ni dentro de `git--diff_last_commit.md`, incluso usando `-f`. Los ejemplos `.env.example`, `.env.sample` y `.env.template` pueden incluirse si no contienen secretos; `--no-env-example` los excluye.

## ⚙️ Configuración Personalizada

- **`.aiignore`**: Permite definir patrones de exclusión simples (tipo `fnmatch`). Lo que coincida no entrará en el ZIP.
- **`.aipass`**: Permite que archivos listados se incluyan sin pasar por el detector de secretos (útil para falsos positivos). El propio archivo `.aipass` nunca entra al ZIP, incluso con `-f`. **Nota importante**: No anula las exclusiones globales de seguridad (como `.git`, `node_modules`, carpetas ocultas tipo `.tmp/` o `.uv-python/`, `.env`, etc.); esos archivos siempre se ignorarán. Se mostrará una advertencia `⚠️` por seguridad.
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

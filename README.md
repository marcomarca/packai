# 📦 Pack AI

**Pack AI** es una herramienta de línea de comandos (CLI) diseñada para empaquetar proyectos en archivos ZIP optimizados para el análisis con modelos de IA (como ChatGPT, Claude o Gemini).

## ✨ Características Principales

- 🛡️ **Escaneo de Secretos Proactivo**: Detecta tokens de API (OpenAI, Groq, Anthropic, AWS, etc.) y asignaciones de variables sensibles en dos capas (Alta Confianza y Contextual).
- 🚀 **Recorrido de Directorios Optimizado**: Ignora carpetas pesadas como `node_modules`, `.venv` o `.git` de forma recursiva sin siquiera entrar en ellas, garantizando una velocidad máxima.
- 📋 **Integración con Portapapeles**: Copia automáticamente el archivo ZIP resultante (o su ruta) al portapapeles de Windows para que solo tengas que hacer `Ctrl+V` en tu chat de IA.
- 🔒 **Seguridad Reforzada**: Salta automáticamente archivos de más de 1MB y enlaces simbólicos (`symlinks`) para evitar fugas de datos accidentales.

## ⚙️ Configuración de Exclusiones

Puedes controlar qué archivos entran en el ZIP y cuáles se analizan mediante dos archivos opcionales:

### 1. `.aiignore` (Exclusión Total)
Los archivos o carpetas que coincidan con los patrones de este archivo **no se incluirán en el ZIP**. Es ideal para dependencias, archivos binarios pesados o carpetas de build.

### 2. `.aipass` (Bypass del Analizador)
Los archivos que coincidan con los patrones de este archivo **se incluirán en el ZIP sin ser analizados por el escáner de secretos**.
Es útil para archivos que contienen patrones que disparan falsos positivos pero que necesitas compartir con la IA (como este propio script).

> [!CAUTION]
> **ADVERTENCIA DE SEGURIDAD**: Los archivos listados en `.aipass` se añadirán "sí o sí" al ZIP sin ninguna verificación. Es extremadamente peligroso añadir aquí archivos que contengan llaves privadas reales, ya que el analizador no te avisará y podrías filtrarlas accidentalmente a la IA.

## 🚀 Instalación

Esta herramienta utiliza [uv](https://github.com/astral-sh/uv) para una gestión de dependencias ultrarrápida.

```bash
git clone <url-del-repo>
cd pack_ai
uv sync
```

## 🛠️ Uso

```bash
uv run python pack_ai.py [opciones] <ruta_del_proyecto>
```

> [!IMPORTANT]
> **Orden de los argumentos**: Para soportar rutas con espacios sin necesidad de comillas, todas las opciones (como `--copy` o `--output`) deben escribirse **antes** de la ruta del proyecto. Cualquier cosa escrita después de la ruta será considerada parte del nombre de la carpeta.

### Ejemplos

```bash
# Uso básico
uv run python pack_ai.py C:\Proyectos\Mi App Increible

# Con opciones (antes de la ruta)
uv run python pack_ai.py --copy path --output backup.zip C:\Proyectos\Mi App
```

### Opciones disponibles

| Opción | Valores | Descripción |
|---|---|---|
| `--copy` | `file`, `path`, `none` | Define qué se copia al portapapeles (por defecto: `file`). |
| `--output` | `[ruta]` | Define la ruta y nombre del ZIP generado (por defecto: carpeta_padre/nombre.zip). |
| `--no-env-example` | (flag) | Si se usa, excluye archivos `.env.example`, `.env.sample` y `.env.template`. |

## 🛡️ Seguridad y Limitaciones

**Pack AI** es una herramienta diseñada para **reducir el riesgo** de incluir secretos en tus paquetes para IA, pero **no garantiza una detección completa del 100%**. 

- El escaneo se basa en patrones de expresiones regulares (regex). No puede detectar secretos en formatos no previstos o claves que no sigan un patrón reconocible.
- El uso de `.aipass` desactiva el escaneo por completo para los archivos indicados.
- Es una herramienta local y auditable: el código es transparente y no realiza peticiones de red.

**Importante**: Revisa siempre el reporte de archivos incluidos y los hallazgos del escáner antes de compartir el contenido con una IA. La responsabilidad final de los datos compartidos es del usuario.

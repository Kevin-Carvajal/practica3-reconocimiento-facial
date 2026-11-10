# Control de asistencia con reconocimiento facial – Práctica 3 CONSOF

## Descripción
Aplicativo web en Django que captura video desde la cámara, detecta rostros con OpenCV
(clasificador Haar), los reconoce con LBPH y **registra automáticamente la asistencia**
de las personas reconocidas. Los datos se guardan en PostgreSQL.

## Integrantes
- Nombre – rol

## Tecnologías
Python, Django, OpenCV (opencv-contrib-python), PostgreSQL

## Funcionamiento de la asistencia
- En cada cuadro del video se detectan los rostros y se obtiene el nombre de cada uno.
- Una persona queda registrada cuando aparece en **5 cuadros consecutivos**; así se evitan
  falsos positivos por un reconocimiento aislado.
- Las etiquetas `Desconocido` y `Sin modelo` se ignoran.
- Cada persona se registra **una sola vez por día** (restricción única en `nombre` + `fecha`).
  La hora guardada es la de su primera entrada.
- Quién ya fue registrado hoy se guarda en memoria para no consultar la base de datos en cada cuadro.
- La fecha y hora usan la zona horaria `America/Guayaquil`.
- Además, cada 30 cuadros se sigue guardando el número de rostros en el modelo `Registro`.

## Instalación
1. Clonar el repositorio.
2. Crear el entorno virtual (no se sube al repositorio): `python -m venv venv`
3. Activarlo e instalar dependencias: `pip install -r requirements.txt`
4. Crear la base de datos `deteccion_db` en PostgreSQL y ajustar usuario y contraseña en `config/settings.py`.
5. Ejecutar migraciones: `python manage.py makemigrations deteccion` y luego `python manage.py migrate`

## Uso
1. Capturar fotos de cada persona (una vez por persona):
   `python entrenar_rostros.py capturar "Nombre Apellido"`
2. Entrenar el modelo (cada vez que se agregan personas):
   `python entrenar_rostros.py entrenar`
3. Iniciar el servidor: `python manage.py runserver`
4. Abrir http://127.0.0.1:8000/ y colocarse frente a la cámara. Al ser reconocida,
   la persona aparece en el panel "Asistentes de hoy" (se actualiza cada 3 segundos).

### Rutas
| Ruta | Descripción |
|------|-------------|
| `/` | Interfaz con el video en vivo y el panel de asistencia |
| `/video_feed/` | Transmisión MJPEG de la cámara |
| `/asistencia/` | Asistentes de hoy en JSON (`total` y lista de `nombre` y `hora`) |
| `/estadisticas/` | Últimos 10 conteos de rostros en JSON |

Ejemplo de respuesta de `/asistencia/`:
```json
{"fecha": "2026-11-10", "total": 1, "asistentes": [{"nombre": "Ana Pérez", "hora": "08:02:15"}]}
```

## Estructura
- `deteccion/camera.py`: captura de video, detección y reconocimiento (`DetectorRostros`, `VideoCamera`)
- `deteccion/reconocimiento.py`: captura de muestras, entrenamiento y predicción LBPH
- `deteccion/asistencia.py`: clase `ControlAsistencia` (frames consecutivos y registro diario)
- `deteccion/models.py`: modelos `Registro` (conteo de rostros) y `Asistencia` (nombre, fecha, hora de entrada)
- `deteccion/views.py`: vistas, transmisión MJPEG, estadísticas y asistencia
- `deteccion/templates/deteccion/index.html`: interfaz web
- `entrenar_rostros.py`: herramienta de línea de comandos para capturar y entrenar

"""Utilidades compartidas por las pruebas: cámara simulada e imágenes sintéticas."""
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from deteccion import reconocimiento


def imagen_negra(alto=480, ancho=640):
    """Frame BGR completamente negro (no contiene rostros)."""
    return np.zeros((alto, ancho, 3), dtype=np.uint8)


def patron_rostro(semilla, tamano=200):
    """Imagen en gris con una textura propia de cada 'persona'.

    LBPH trabaja con texturas, así que dos semillas distintas producen
    patrones que el modelo puede diferenciar.
    """
    generador = np.random.default_rng(semilla)
    bloque = 20
    base = generador.integers(0, 256, (tamano // bloque, tamano // bloque), dtype=np.uint8)
    return np.kron(base, np.ones((bloque, bloque), dtype=np.uint8))


class CamaraFalsa:
    """Sustituye a VideoCamera: devuelve una secuencia fija de frames.

    `secuencia` es una lista de listas de nombres, una por frame. Cuando se
    acaba, devuelve (None, 0, []) como si la cámara se hubiera desconectado.
    """

    JPEG = b"\xff\xd8\xff\xe0FAKEJPEG\xff\xd9"

    def __init__(self, secuencia):
        self.secuencia = list(secuencia)

    def obtener_frame(self):
        if not self.secuencia:
            return None, 0, []
        nombres = self.secuencia.pop(0)
        return self.JPEG, len(nombres), nombres


def consumir_stream(respuesta):
    """Lee todo el contenido de una StreamingHttpResponse y lo devuelve en bytes."""
    return b"".join(respuesta.streaming_content)


class ArchivosTemporalesMixin:
    """Redirige carpeta de fotos, modelo y etiquetas a un directorio temporal.

    Así las pruebas no leen ni sobrescriben el modelo real del proyecto.
    """

    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        rutas = {
            "CARPETA_ROSTROS": self.tmp / "rostros",
            "ARCHIVO_MODELO": self.tmp / "modelo.yml",
            "ARCHIVO_ETIQUETAS": self.tmp / "etiquetas.json",
        }
        for nombre, ruta in rutas.items():
            parche = mock.patch.object(reconocimiento, nombre, ruta)
            parche.start()
            self.addCleanup(parche.stop)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def crear_fotos(self, nombre, semilla, cantidad=5):
        """Guarda fotos sintéticas de una persona en la carpeta de entrenamiento."""
        carpeta = reconocimiento.CARPETA_ROSTROS / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        base = patron_rostro(semilla)
        for i in range(cantidad):
            # Cambios de brillo, como fotos tomadas con distinta iluminación.
            variacion = np.clip(base.astype(int) + (i - 2) * 4, 0, 255).astype(np.uint8)
            cv2.imwrite(str(carpeta / f"{nombre}_{i:03d}.jpg"), variacion)

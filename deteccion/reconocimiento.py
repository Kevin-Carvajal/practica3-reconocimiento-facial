"""Reconocimiento facial con LBPH (requiere opencv-contrib-python).

Flujo:
1. capturar_muestras(nombre): guarda recortes de rostro de una persona.
2. entrenar(): crea el modelo LBPH a partir de todas las carpetas.
3. ReconocedorRostros.predecir(): devuelve el nombre de un rostro detectado.
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
CARPETA_ROSTROS = BASE_DIR / "rostros_entrenamiento"
ARCHIVO_MODELO = BASE_DIR / "modelo_lbph.yml"
ARCHIVO_ETIQUETAS = BASE_DIR / "etiquetas.json"

TAMANO = (200, 200)
# En LBPH, un valor menor significa más parecido. Por encima de este umbral se considera desconocido.
UMBRAL_CONFIANZA = 80.0


class ReconocedorRostros:
    """Carga el modelo entrenado y asigna un nombre a cada rostro."""

    def __init__(self):
        self.modelo = None
        self.etiquetas = {}
        if ARCHIVO_MODELO.exists() and ARCHIVO_ETIQUETAS.exists():
            self.modelo = cv2.face.LBPHFaceRecognizer_create()
            self.modelo.read(str(ARCHIVO_MODELO))
            datos = json.loads(ARCHIVO_ETIQUETAS.read_text(encoding="utf-8"))
            self.etiquetas = {int(k): v for k, v in datos.items()}

    def predecir(self, gris, rostro):
        """Devuelve (nombre, confianza) para un rostro (x, y, w, h) en una imagen en gris."""
        if self.modelo is None:
            return "Sin modelo", None
        x, y, w, h = rostro
        recorte = cv2.resize(gris[y:y + h, x:x + w], TAMANO)
        etiqueta, confianza = self.modelo.predict(recorte)
        if confianza > UMBRAL_CONFIANZA:
            return "Desconocido", confianza
        return self.etiquetas.get(etiqueta, "Desconocido"), confianza


def entrenar():
    """Lee las fotos de cada carpeta y guarda el modelo y las etiquetas."""
    imagenes, indices = [], []
    nombres = {}
    carpetas = sorted(p for p in CARPETA_ROSTROS.iterdir() if p.is_dir())
    for indice, carpeta in enumerate(carpetas):
        nombres[indice] = carpeta.name
        for foto in carpeta.glob("*.jpg"):
            img = cv2.imread(str(foto), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                imagenes.append(cv2.resize(img, TAMANO))
                indices.append(indice)

    if not imagenes:
        raise RuntimeError("No hay fotos en rostros_entrenamiento/. Captura muestras primero.")

    modelo = cv2.face.LBPHFaceRecognizer_create()
    modelo.train(imagenes, np.array(indices))
    modelo.write(str(ARCHIVO_MODELO))
    ARCHIVO_ETIQUETAS.write_text(json.dumps(nombres, ensure_ascii=False), encoding="utf-8")
    return len(imagenes), nombres


def capturar_muestras(nombre, cantidad=40):
    """Abre la cámara y guarda recortes de rostro de la persona indicada.

    Solo guarda una muestra cuando hay exactamente un rostro en el cuadro.
    """
    carpeta = CARPETA_ROSTROS / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    camara = cv2.VideoCapture(0)
    guardadas = 0
    try:
        while guardadas < cantidad:
            ok, frame = camara.read()
            if not ok:
                raise RuntimeError("No se pudo leer la cámara.")
            gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rostros = detector.detectMultiScale(gris, 1.1, 5)
            if len(rostros) == 1:
                x, y, w, h = rostros[0]
                recorte = cv2.resize(gris[y:y + h, x:x + w], TAMANO)
                cv2.imwrite(str(carpeta / f"{nombre}_{guardadas:03d}.jpg"), recorte)
                guardadas += 1
                time.sleep(0.15)  # separa las muestras para que no sean casi idénticas
    finally:
        camara.release()
    return guardadas

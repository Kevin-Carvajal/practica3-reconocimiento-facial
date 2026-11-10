"""Captura de video, detección y reconocimiento de rostros con OpenCV."""
import cv2

from .reconocimiento import ReconocedorRostros

COLOR = (0, 255, 0)


class DetectorRostros:
    """Detecta rostros con el clasificador Haar y los identifica con LBPH."""

    def __init__(self):
        ruta = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.clasificador = cv2.CascadeClassifier(ruta)
        self.reconocedor = ReconocedorRostros()

    def detectar(self, gris):
        """Devuelve la lista de rostros (x, y, w, h) en una imagen en escala de grises."""
        return self.clasificador.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5)

    def identificar(self, gris, rostros):
        """Devuelve el nombre de cada rostro, en el mismo orden que `rostros`."""
        return [self.reconocedor.predecir(gris, rostro)[0] for rostro in rostros]

    @staticmethod
    def dibujar(frame, rostros, nombres):
        """Dibuja un recuadro con el nombre de cada persona y el conteo total."""
        for (x, y, w, h), nombre in zip(rostros, nombres):
            cv2.rectangle(frame, (x, y), (x + w, y + h), COLOR, 2)
            cv2.putText(frame, nombre, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR, 2)
        cv2.putText(frame, f"Rostros: {len(rostros)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, COLOR, 2)
        return frame


class VideoCamera:
    """Lee la cámara, aplica detección y reconocimiento y devuelve frames JPEG."""

    def __init__(self, indice=0):
        self.captura = cv2.VideoCapture(indice)
        self.detector = DetectorRostros()

    def __del__(self):
        if hasattr(self, "captura"):
            self.captura.release()

    def obtener_frame(self):
        """Lee y procesa un frame de la cámara.

        Devuelve (jpeg_bytes, cantidad_rostros, lista_de_nombres),
        o (None, 0, []) si la cámara o la codificación fallan.
        """
        ok, frame = self.captura.read()
        if not ok:
            return None, 0, []
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = self.detector.detectar(gris)
        nombres = self.detector.identificar(gris, rostros)
        self.detector.dibujar(frame, rostros, nombres)
        ok, jpeg = cv2.imencode(".jpg", frame)
        if not ok:
            return None, 0, []
        return jpeg.tobytes(), len(rostros), nombres

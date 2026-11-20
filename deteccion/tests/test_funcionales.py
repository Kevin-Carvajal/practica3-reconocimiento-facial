"""Pruebas funcionales: casos de uso clave vistos desde el usuario.

CU-01 Inicio del sistema
CU-02 Detección y reconocimiento en el video (registro de asistencia)
CU-03 Visualización de resultados en la interfaz

En CU-02 se usa el flujo completo de VideoCamera: lectura del frame,
reconocimiento LBPH con un modelo entrenado, dibujo, codificación JPEG,
vista de Django y base de datos. Solo se simulan la webcam y la ubicación
del rostro en la imagen, porque las pruebas no tienen cámara ni rostros reales.
"""
from unittest import mock

import cv2
import numpy as np
from django.test import TestCase
from django.urls import reverse

from deteccion import reconocimiento, views
from deteccion.asistencia import FRAMES_CONSECUTIVOS
from deteccion.camera import VideoCamera
from deteccion.models import Asistencia

from .utilidades import ArchivosTemporalesMixin, CamaraFalsa, consumir_stream, patron_rostro

CAJA_ROSTRO = (100, 50, 200, 200)  # x, y, w, h


def frame_con_persona(semilla):
    """Frame BGR de 640x480 con el 'rostro' de una persona en CAJA_ROSTRO."""
    gris = np.zeros((480, 640), dtype=np.uint8)
    x, y, w, h = CAJA_ROSTRO
    gris[y:y + h, x:x + w] = patron_rostro(semilla)
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)


class CU01InicioTests(TestCase):
    """El usuario abre http://127.0.0.1:8000/ y ve la interfaz lista para usar."""

    def test_la_pagina_principal_carga_con_sus_secciones(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn("Control de asistencia por reconocimiento facial", html)
        self.assertIn("EN VIVO", html)
        self.assertIn("Asistentes de hoy", html)
        self.assertIn('id="tabla-asistentes"', html)

    def test_al_iniciar_el_dia_no_hay_asistentes(self):
        datos = self.client.get("/asistencia/").json()
        self.assertEqual(datos["total"], 0)


class CU02DeteccionEnVideoTests(ArchivosTemporalesMixin, TestCase):
    """Una persona registrada se pone frente a la cámara y queda su asistencia."""

    def setUp(self):
        super().setUp()
        self.crear_fotos("Ana Perez", semilla=1)
        self.crear_fotos("Luis Mora", semilla=2)
        reconocimiento.entrenar()

    def camara_con_frames(self, frames):
        """VideoCamera real con la webcam sustituida por una lista de frames."""
        lecturas = [(True, f) for f in frames] + [(False, None)]
        with mock.patch("deteccion.camera.cv2.VideoCapture") as captura:
            captura.return_value.read.side_effect = lecturas
            camara = VideoCamera()
        camara.detector.detectar = lambda gris: [CAJA_ROSTRO]
        return camara

    def transmitir(self, camara):
        with mock.patch.object(views, "VideoCamera", return_value=camara):
            return consumir_stream(self.client.get(reverse("video_feed")))

    def test_persona_reconocida_queda_registrada(self):
        camara = self.camara_con_frames([frame_con_persona(2)] * FRAMES_CONSECUTIVOS)
        contenido = self.transmitir(camara)

        self.assertEqual(contenido.count(b"--frame"), FRAMES_CONSECUTIVOS)
        self.assertEqual(list(Asistencia.objects.values_list("nombre", flat=True)),
                         ["Luis Mora"])

    def test_aparicion_breve_no_registra_asistencia(self):
        camara = self.camara_con_frames(
            [frame_con_persona(1)] * (FRAMES_CONSECUTIVOS - 1))
        self.transmitir(camara)
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_persona_no_registrada_no_genera_asistencia(self):
        # Persona cuyo rostro no está en el entrenamiento: LBPH la marca "Desconocido".
        camara = self.camara_con_frames([frame_con_persona(99)] * 10)
        self.transmitir(camara)
        self.assertEqual(Asistencia.objects.count(), 0)


class CU03VisualizacionTests(TestCase):
    """Tras la detección, el panel 'Asistentes de hoy' muestra a las personas."""

    def test_el_panel_muestra_a_quien_paso_por_la_camara(self):
        secuencia = [["Ana Perez"]] * 5 + [["Ana Perez", "Luis Mora"]] * 5
        with mock.patch.object(views, "VideoCamera", return_value=CamaraFalsa(secuencia)):
            consumir_stream(self.client.get("/video_feed/"))

        # Es la misma consulta que hace index.html cada 3 segundos.
        datos = self.client.get("/asistencia/").json()
        self.assertEqual(datos["total"], 2)
        self.assertEqual([a["nombre"] for a in datos["asistentes"]],
                         ["Ana Perez", "Luis Mora"])
        for asistente in datos["asistentes"]:
            self.assertRegex(asistente["hora"], r"^\d{2}:\d{2}:\d{2}$")

    def test_una_persona_aparece_una_sola_vez_en_el_panel(self):
        with mock.patch.object(views, "VideoCamera",
                               return_value=CamaraFalsa([["Ana Perez"]] * 20)):
            consumir_stream(self.client.get("/video_feed/"))
        # Se vuelve a abrir la transmisión (por ejemplo, al recargar la página).
        with mock.patch.object(views, "VideoCamera",
                               return_value=CamaraFalsa([["Ana Perez"]] * 20)):
            consumir_stream(self.client.get("/video_feed/"))

        self.assertEqual(self.client.get("/asistencia/").json()["total"], 1)

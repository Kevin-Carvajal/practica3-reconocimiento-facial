"""Pruebas unitarias de las funciones críticas del sistema.

Cubren, cada una por separado y sin cámara real:
- ControlAsistencia (frames consecutivos, registro diario, nombres ignorados)
- Reconocimiento LBPH (entrenar y predecir)
- DetectorRostros y VideoCamera (detección, dibujo y codificación JPEG)
- Modelos Registro y Asistencia
"""
import datetime
import json
from unittest import mock

import cv2
import numpy as np
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from deteccion import reconocimiento
from deteccion.asistencia import ControlAsistencia, FRAMES_CONSECUTIVOS
from deteccion.camera import COLOR, DetectorRostros, VideoCamera
from deteccion.models import Asistencia, Registro

from .utilidades import ArchivosTemporalesMixin, imagen_negra, patron_rostro


# ---------------------------------------------------------------------------
# ControlAsistencia
# ---------------------------------------------------------------------------
class ControlAsistenciaTests(TestCase):

    def procesar_n(self, control, nombres, n):
        registrados = []
        for _ in range(n):
            registrados.extend(control.procesar(nombres))
        return registrados

    def test_no_registra_antes_de_los_frames_requeridos(self):
        control = ControlAsistencia()
        registrados = self.procesar_n(control, ["Ana"], FRAMES_CONSECUTIVOS - 1)
        self.assertEqual(registrados, [])
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_registra_al_completar_los_frames_consecutivos(self):
        control = ControlAsistencia()
        registrados = self.procesar_n(control, ["Ana"], FRAMES_CONSECUTIVOS)
        self.assertEqual(registrados, ["Ana"])
        self.assertTrue(Asistencia.objects.filter(nombre="Ana").exists())

    def test_la_racha_se_reinicia_si_la_persona_desaparece(self):
        control = ControlAsistencia(frames_requeridos=3)
        control.procesar(["Ana"])
        control.procesar(["Ana"])
        control.procesar([])            # Ana no aparece: pierde la racha
        control.procesar(["Ana"])
        control.procesar(["Ana"])
        self.assertEqual(Asistencia.objects.count(), 0)
        self.assertEqual(control.procesar(["Ana"]), ["Ana"])

    def test_ignora_desconocido_y_sin_modelo(self):
        control = ControlAsistencia(frames_requeridos=1)
        registrados = control.procesar(["Desconocido", "Sin modelo"])
        self.assertEqual(registrados, [])
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_registra_una_sola_vez_por_dia(self):
        control = ControlAsistencia(frames_requeridos=2)
        self.procesar_n(control, ["Ana"], 10)
        self.assertEqual(Asistencia.objects.filter(nombre="Ana").count(), 1)

    def test_varias_personas_en_el_mismo_frame(self):
        control = ControlAsistencia(frames_requeridos=2)
        registrados = self.procesar_n(control, ["Ana", "Luis"], 2)
        self.assertCountEqual(registrados, ["Ana", "Luis"])

    def test_carga_los_registrados_previos_de_la_base(self):
        Asistencia.objects.create(nombre="Ana", fecha=datetime.date.today())
        with mock.patch("deteccion.asistencia.timezone.localdate",
                        return_value=datetime.date.today()):
            control = ControlAsistencia(frames_requeridos=1)
            self.assertIn("Ana", control.registrados_hoy)
            self.assertEqual(control.procesar(["Ana"]), [])
        self.assertEqual(Asistencia.objects.count(), 1)

    def test_al_cambiar_el_dia_se_puede_registrar_de_nuevo(self):
        dia1 = datetime.date(2026, 11, 18)
        dia2 = datetime.date(2026, 11, 19)
        with mock.patch("deteccion.asistencia.timezone.localdate") as fecha:
            fecha.return_value = dia1
            control = ControlAsistencia(frames_requeridos=1)
            self.assertEqual(control.procesar(["Ana"]), ["Ana"])
            fecha.return_value = dia2
            self.assertEqual(control.procesar(["Ana"]), ["Ana"])
        self.assertEqual(
            list(Asistencia.objects.order_by("fecha").values_list("fecha", flat=True)),
            [dia1, dia2],
        )


# ---------------------------------------------------------------------------
# Reconocimiento LBPH
# ---------------------------------------------------------------------------
class ReconocimientoTests(ArchivosTemporalesMixin, SimpleTestCase):

    def test_sin_modelo_devuelve_sin_modelo(self):
        reconocedor = reconocimiento.ReconocedorRostros()
        gris = np.zeros((300, 300), dtype=np.uint8)
        self.assertEqual(reconocedor.predecir(gris, (0, 0, 200, 200)), ("Sin modelo", None))

    def test_entrenar_sin_fotos_lanza_error(self):
        reconocimiento.CARPETA_ROSTROS.mkdir(parents=True)
        with self.assertRaises(RuntimeError):
            reconocimiento.entrenar()

    def test_entrenar_genera_modelo_y_etiquetas(self):
        self.crear_fotos("Ana", semilla=1)
        self.crear_fotos("Luis", semilla=2)
        total, nombres = reconocimiento.entrenar()
        self.assertEqual(total, 10)
        self.assertEqual(nombres, {0: "Ana", 1: "Luis"})
        self.assertTrue(reconocimiento.ARCHIVO_MODELO.exists())
        etiquetas = json.loads(reconocimiento.ARCHIVO_ETIQUETAS.read_text(encoding="utf-8"))
        self.assertEqual(etiquetas, {"0": "Ana", "1": "Luis"})

    def test_predice_el_nombre_correcto(self):
        self.crear_fotos("Ana", semilla=1)
        self.crear_fotos("Luis", semilla=2)
        reconocimiento.entrenar()
        reconocedor = reconocimiento.ReconocedorRostros()

        # Se pega el "rostro" de Luis dentro de una imagen más grande.
        gris = np.zeros((400, 400), dtype=np.uint8)
        gris[50:250, 100:300] = patron_rostro(2)
        nombre, confianza = reconocedor.predecir(gris, (100, 50, 200, 200))
        self.assertEqual(nombre, "Luis")
        self.assertLessEqual(confianza, reconocimiento.UMBRAL_CONFIANZA)

    def test_rostro_no_entrenado_es_desconocido(self):
        self.crear_fotos("Ana", semilla=1)
        self.crear_fotos("Luis", semilla=2)
        reconocimiento.entrenar()
        reconocedor = reconocimiento.ReconocedorRostros()
        nombre, confianza = reconocedor.predecir(patron_rostro(99), (0, 0, 200, 200))
        self.assertEqual(nombre, "Desconocido")
        self.assertGreater(confianza, reconocimiento.UMBRAL_CONFIANZA)

    def test_sobre_el_umbral_devuelve_desconocido(self):
        self.crear_fotos("Ana", semilla=1)
        reconocimiento.entrenar()
        reconocedor = reconocimiento.ReconocedorRostros()
        gris = patron_rostro(1)
        with mock.patch.object(reconocimiento, "UMBRAL_CONFIANZA", -1.0):
            nombre, _ = reconocedor.predecir(gris, (0, 0, 200, 200))
        self.assertEqual(nombre, "Desconocido")


class CapturarMuestrasTests(ArchivosTemporalesMixin, SimpleTestCase):
    """capturar_muestras() con la webcam y el detector simulados."""

    def capturar(self, lecturas, rostros_por_frame, cantidad):
        with mock.patch.object(reconocimiento.cv2, "VideoCapture") as captura, \
                mock.patch.object(reconocimiento.cv2, "CascadeClassifier") as clasificador, \
                mock.patch.object(reconocimiento.time, "sleep"):
            captura.return_value.read.side_effect = lecturas
            clasificador.return_value.detectMultiScale.side_effect = rostros_por_frame
            try:
                return reconocimiento.capturar_muestras("Ana", cantidad=cantidad)
            finally:
                self.camara = captura.return_value

    def test_solo_guarda_frames_con_un_unico_rostro(self):
        frame = imagen_negra()
        un_rostro = [(10, 10, 100, 100)]
        dos_rostros = [(10, 10, 100, 100), (300, 10, 100, 100)]
        guardadas = self.capturar(
            lecturas=[(True, frame)] * 4,
            rostros_por_frame=[un_rostro, [], dos_rostros, un_rostro],
            cantidad=2,
        )
        self.assertEqual(guardadas, 2)
        fotos = sorted(p.name for p in (reconocimiento.CARPETA_ROSTROS / "Ana").iterdir())
        self.assertEqual(fotos, ["Ana_000.jpg", "Ana_001.jpg"])
        self.camara.release.assert_called_once()

    def test_error_de_camara_lanza_excepcion_y_libera_la_camara(self):
        with self.assertRaises(RuntimeError):
            self.capturar(lecturas=[(False, None)], rostros_por_frame=[], cantidad=1)
        self.camara.release.assert_called_once()


# ---------------------------------------------------------------------------
# DetectorRostros y VideoCamera
# ---------------------------------------------------------------------------
class DetectorRostrosTests(ArchivosTemporalesMixin, SimpleTestCase):

    def test_carga_el_clasificador_haar(self):
        detector = DetectorRostros()
        self.assertFalse(detector.clasificador.empty())

    def test_imagen_sin_rostros_devuelve_lista_vacia(self):
        detector = DetectorRostros()
        gris = cv2.cvtColor(imagen_negra(), cv2.COLOR_BGR2GRAY)
        self.assertEqual(len(detector.detectar(gris)), 0)

    def test_identificar_conserva_el_orden_de_los_rostros(self):
        detector = DetectorRostros()
        detector.reconocedor = mock.Mock()
        detector.reconocedor.predecir.side_effect = [("Ana", 30.0), ("Luis", 40.0)]
        nombres = detector.identificar(None, [(0, 0, 10, 10), (20, 20, 10, 10)])
        self.assertEqual(nombres, ["Ana", "Luis"])

    def test_dibujar_marca_el_recuadro_del_rostro(self):
        frame = imagen_negra()
        DetectorRostros.dibujar(frame, [(100, 100, 80, 80)], ["Ana"])
        # La esquina superior izquierda del recuadro queda pintada con el color verde.
        self.assertEqual(tuple(int(c) for c in frame[100, 100]), COLOR)


class VideoCameraTests(ArchivosTemporalesMixin, SimpleTestCase):

    def crear_camara(self, lectura):
        with mock.patch("deteccion.camera.cv2.VideoCapture") as captura:
            captura.return_value.read.return_value = lectura
            return VideoCamera()

    def test_frame_valido_devuelve_jpeg(self):
        camara = self.crear_camara((True, imagen_negra()))
        jpeg, cantidad, nombres = camara.obtener_frame()
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))   # cabecera de un JPEG
        self.assertEqual(cantidad, 0)
        self.assertEqual(nombres, [])

    def test_falla_de_lectura_devuelve_none(self):
        camara = self.crear_camara((False, None))
        self.assertEqual(camara.obtener_frame(), (None, 0, []))

    def test_falla_de_codificacion_devuelve_none(self):
        camara = self.crear_camara((True, imagen_negra()))
        with mock.patch("deteccion.camera.cv2.imencode", return_value=(False, None)):
            self.assertEqual(camara.obtener_frame(), (None, 0, []))

    def test_detecta_e_identifica_en_cada_frame(self):
        camara = self.crear_camara((True, imagen_negra()))
        camara.detector.detectar = mock.Mock(return_value=[(10, 10, 50, 50)])
        camara.detector.identificar = mock.Mock(return_value=["Ana"])
        _, cantidad, nombres = camara.obtener_frame()
        self.assertEqual((cantidad, nombres), (1, ["Ana"]))


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class ModelosTests(TestCase):

    def test_asistencia_unica_por_persona_y_dia(self):
        hoy = datetime.date(2026, 11, 19)
        Asistencia.objects.create(nombre="Ana", fecha=hoy)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Asistencia.objects.create(nombre="Ana", fecha=hoy)

    def test_misma_persona_en_dias_distintos(self):
        Asistencia.objects.create(nombre="Ana", fecha=datetime.date(2026, 11, 18))
        Asistencia.objects.create(nombre="Ana", fecha=datetime.date(2026, 11, 19))
        self.assertEqual(Asistencia.objects.count(), 2)

    def test_str_de_los_modelos(self):
        a = Asistencia.objects.create(nombre="Ana", fecha=datetime.date(2026, 11, 19))
        self.assertEqual(str(a), "Ana - 2026-11-19")
        r = Registro.objects.create(rostros=3)
        self.assertTrue(str(r).endswith("3 rostro(s)"))

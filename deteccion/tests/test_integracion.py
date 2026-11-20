"""Pruebas de integración: rutas de Django + vistas + modelos + plantilla.

La cámara se sustituye por CamaraFalsa; el resto del flujo (URLs, vistas,
ControlAsistencia y base de datos) se ejecuta de verdad.
"""
import datetime
from unittest import mock

from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from deteccion import views
from deteccion.models import Asistencia, Registro

from .utilidades import CamaraFalsa, consumir_stream


class RutasTests(TestCase):

    def test_cada_ruta_apunta_a_su_vista(self):
        casos = {
            "/": views.index,
            "/video_feed/": views.video_feed,
            "/estadisticas/": views.estadisticas,
            "/asistencia/": views.asistencia,
        }
        for ruta, vista in casos.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(resolve(ruta).func, vista)

    def test_nombres_de_rutas(self):
        self.assertEqual(reverse("index"), "/")
        self.assertEqual(reverse("video_feed"), "/video_feed/")
        self.assertEqual(reverse("estadisticas"), "/estadisticas/")
        self.assertEqual(reverse("asistencia"), "/asistencia/")

    def test_ruta_inexistente_devuelve_404(self):
        self.assertEqual(self.client.get("/no-existe/").status_code, 404)


class IndexTests(TestCase):

    def test_index_responde_y_usa_la_plantilla(self):
        respuesta = self.client.get(reverse("index"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "deteccion/index.html")

    def test_index_enlaza_el_video_y_la_api_de_asistencia(self):
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn('src="/video_feed/"', html)
        self.assertIn('"/asistencia/"', html)
        self.assertIn('href="/estadisticas/"', html)


class AsistenciaApiTests(TestCase):

    def test_sin_asistentes(self):
        datos = self.client.get(reverse("asistencia")).json()
        self.assertEqual(datos["total"], 0)
        self.assertEqual(datos["asistentes"], [])
        self.assertEqual(datos["fecha"], timezone.localdate().isoformat())

    def test_solo_devuelve_los_asistentes_de_hoy(self):
        hoy = timezone.localdate()
        Asistencia.objects.create(nombre="Ana", fecha=hoy)
        Asistencia.objects.create(nombre="Luis", fecha=hoy)
        Asistencia.objects.create(nombre="Ayer", fecha=hoy - datetime.timedelta(days=1))

        datos = self.client.get(reverse("asistencia")).json()
        self.assertEqual(datos["total"], 2)
        self.assertEqual([a["nombre"] for a in datos["asistentes"]], ["Ana", "Luis"])

    def test_hora_en_formato_local(self):
        a = Asistencia.objects.create(nombre="Ana", fecha=timezone.localdate())
        esperado = timezone.localtime(a.hora_entrada).strftime("%H:%M:%S")
        datos = self.client.get(reverse("asistencia")).json()
        self.assertEqual(datos["asistentes"][0]["hora"], esperado)


class EstadisticasApiTests(TestCase):

    def test_devuelve_maximo_10_registros_del_mas_reciente_al_mas_antiguo(self):
        for i in range(12):
            Registro.objects.create(rostros=i)
        datos = self.client.get(reverse("estadisticas")).json()["ultimos_registros"]
        self.assertEqual(len(datos), 10)
        fechas = [d["fecha"] for d in datos]
        self.assertEqual(fechas, sorted(fechas, reverse=True))


class VideoFeedTests(TestCase):
    """Transmisión MJPEG + registro de asistencia + guardado periódico del conteo."""

    def transmitir(self, secuencia):
        with mock.patch.object(views, "VideoCamera", return_value=CamaraFalsa(secuencia)):
            respuesta = self.client.get(reverse("video_feed"))
            contenido = consumir_stream(respuesta)
        return respuesta, contenido

    def test_tipo_de_contenido_mjpeg(self):
        respuesta, contenido = self.transmitir([["Ana"]] * 3)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"],
                         "multipart/x-mixed-replace; boundary=frame")
        self.assertEqual(contenido.count(b"--frame"), 3)
        self.assertIn(CamaraFalsa.JPEG, contenido)

    def test_el_stream_registra_la_asistencia(self):
        self.transmitir([["Ana"]] * 5)
        self.assertTrue(Asistencia.objects.filter(
            nombre="Ana", fecha=timezone.localdate()).exists())

    def test_guarda_el_conteo_cada_30_frames(self):
        self.transmitir([["Ana", "Luis"]] * 65)
        self.assertEqual(Registro.objects.count(), 2)
        self.assertEqual(Registro.objects.first().rostros, 2)

    def test_el_stream_termina_si_falla_la_camara(self):
        _, contenido = self.transmitir([])
        self.assertEqual(contenido, b"")

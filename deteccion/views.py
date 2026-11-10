from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone

from .asistencia import ControlAsistencia
from .camera import VideoCamera
from .models import Asistencia, Registro

GUARDAR_CADA_N_FRAMES = 30


def index(request):
    """Página principal con el video en vivo y el panel de asistencia."""
    return render(request, "deteccion/index.html")


def _generar_frames(camara):
    """Genera el flujo MJPEG, registra asistencias y guarda el conteo periódicamente."""
    control = ControlAsistencia()
    contador = 0
    while True:
        frame, rostros, nombres = camara.obtener_frame()
        if frame is None:
            break
        control.procesar(nombres)
        contador += 1
        if contador % GUARDAR_CADA_N_FRAMES == 0:
            Registro.objects.create(rostros=rostros)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"


def video_feed(request):
    """Transmisión de la cámara como multipart/x-mixed-replace."""
    return StreamingHttpResponse(
        _generar_frames(VideoCamera()),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )


def estadisticas(request):
    """Últimos 10 conteos de rostros en JSON."""
    ultimos = Registro.objects.all()[:10]
    datos = [{"fecha": r.fecha.isoformat(), "rostros": r.rostros} for r in ultimos]
    return JsonResponse({"ultimos_registros": datos})


def asistencia(request):
    """Asistentes de hoy (nombre y hora de entrada en hora local) en JSON."""
    hoy = timezone.localdate()
    registros = Asistencia.objects.filter(fecha=hoy)
    asistentes = [
        {
            "nombre": a.nombre,
            "hora": timezone.localtime(a.hora_entrada).strftime("%H:%M:%S"),
        }
        for a in registros
    ]
    return JsonResponse({
        "fecha": hoy.isoformat(),
        "total": len(asistentes),
        "asistentes": asistentes,
    })

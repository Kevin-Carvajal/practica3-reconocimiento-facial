"""Control de asistencia a partir de los nombres reconocidos en el video."""
from django.utils import timezone

from .models import Asistencia

# Una persona debe aparecer en este número de frames seguidos para registrar su asistencia.
FRAMES_CONSECUTIVOS = 5

# Etiquetas del reconocedor que no corresponden a una persona real.
NOMBRES_IGNORADOS = {"Desconocido", "Sin modelo"}


class ControlAsistencia:
    """Registra la entrada de cada persona una sola vez por día.

    Para evitar falsos positivos, la asistencia solo se guarda cuando la persona
    aparece en FRAMES_CONSECUTIVOS frames seguidos. Quién ya fue registrado hoy se
    guarda en memoria para no consultar la base de datos en cada frame.
    """

    def __init__(self, frames_requeridos=FRAMES_CONSECUTIVOS):
        self.frames_requeridos = frames_requeridos
        self.consecutivos = {}  # nombre -> frames seguidos en los que apareció
        self.fecha_actual = timezone.localdate()
        self.registrados_hoy = self._cargar_registrados(self.fecha_actual)

    @staticmethod
    def _cargar_registrados(fecha):
        """Devuelve el conjunto de nombres que ya tienen asistencia en la fecha dada."""
        return set(
            Asistencia.objects.filter(fecha=fecha).values_list("nombre", flat=True)
        )

    def _actualizar_dia(self):
        """Si cambió el día, reinicia la memoria de registrados."""
        hoy = timezone.localdate()
        if hoy != self.fecha_actual:
            self.fecha_actual = hoy
            self.consecutivos.clear()
            self.registrados_hoy = self._cargar_registrados(hoy)

    def procesar(self, nombres):
        """Procesa los nombres reconocidos en un frame.

        Devuelve la lista de nombres cuya asistencia se registró en este frame.
        """
        self._actualizar_dia()
        presentes = {n for n in nombres if n not in NOMBRES_IGNORADOS}

        # Quien no aparece en este frame pierde su racha de frames consecutivos.
        for nombre in list(self.consecutivos):
            if nombre not in presentes:
                del self.consecutivos[nombre]

        nuevos = []
        for nombre in presentes:
            if nombre in self.registrados_hoy:
                continue
            self.consecutivos[nombre] = self.consecutivos.get(nombre, 0) + 1
            if self.consecutivos[nombre] >= self.frames_requeridos:
                self._registrar(nombre)
                nuevos.append(nombre)
        return nuevos

    def _registrar(self, nombre):
        """Guarda la asistencia (si no existe) y la marca en memoria."""
        Asistencia.objects.get_or_create(nombre=nombre, fecha=self.fecha_actual)
        self.registrados_hoy.add(nombre)
        self.consecutivos.pop(nombre, None)

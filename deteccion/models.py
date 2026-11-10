from django.db import models


class Registro(models.Model):
    """Conteo periódico de rostros detectados en la transmisión."""

    fecha = models.DateTimeField(auto_now_add=True)
    rostros = models.PositiveIntegerField()

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M:%S} - {self.rostros} rostro(s)"


class Asistencia(models.Model):
    """Entrada de una persona reconocida. Solo puede existir una por persona y día."""

    nombre = models.CharField(max_length=100)
    fecha = models.DateField()
    hora_entrada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["hora_entrada"]
        constraints = [
            models.UniqueConstraint(
                fields=["nombre", "fecha"], name="asistencia_unica_por_dia"
            ),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.fecha:%Y-%m-%d}"

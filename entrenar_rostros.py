"""Herramienta de línea de comandos para capturar muestras y entrenar el reconocedor.

Uso:
    python entrenar_rostros.py capturar "Nombre Apellido"
    python entrenar_rostros.py entrenar
"""
import sys

from deteccion.reconocimiento import capturar_muestras, entrenar


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "capturar":
        guardadas = capturar_muestras(sys.argv[2])
        print(f"Se guardaron {guardadas} muestras de {sys.argv[2]}.")
    elif len(sys.argv) == 2 and sys.argv[1] == "entrenar":
        imagenes, nombres = entrenar()
        print(f"Modelo entrenado con {imagenes} imágenes: {nombres}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

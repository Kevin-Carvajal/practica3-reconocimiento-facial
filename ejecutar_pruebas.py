"""Ejecuta todas las pruebas, mide la cobertura y guarda la evidencia en reportes/.

Uso:
    python ejecutar_pruebas.py

Genera:
    reportes/log_pruebas.txt   salida detallada de cada prueba (para el informe)
    reportes/cobertura.txt     porcentaje de código cubierto por archivo
    reportes/cobertura_html/   reporte de cobertura navegable (abrir index.html)
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORTES = BASE / "reportes"
FUENTES = "deteccion"
OMITIR = "*/migrations/*,*/tests/*"


def ejecutar(comando):
    return subprocess.run(comando, cwd=BASE, capture_output=True, text=True)


def main():
    REPORTES.mkdir(exist_ok=True)
    pruebas = ejecutar([
        sys.executable, "-m", "coverage", "run", f"--source={FUENTES}", f"--omit={OMITIR}",
        "manage.py", "test", "--settings=config.settings_test", "-v", "2",
    ])
    salida = pruebas.stdout + pruebas.stderr
    encabezado = f"Fecha de ejecución: {datetime.now():%Y-%m-%d %H:%M:%S}\n" + "=" * 70 + "\n"
    (REPORTES / "log_pruebas.txt").write_text(encabezado + salida, encoding="utf-8")
    print(salida)

    cobertura = ejecutar([sys.executable, "-m", "coverage", "report", "-m"])
    (REPORTES / "cobertura.txt").write_text(cobertura.stdout, encoding="utf-8")
    ejecutar([sys.executable, "-m", "coverage", "html", "-d", str(REPORTES / "cobertura_html")])
    print(cobertura.stdout)
    print(f"Evidencias guardadas en {REPORTES}")
    sys.exit(pruebas.returncode)


if __name__ == "__main__":
    main()

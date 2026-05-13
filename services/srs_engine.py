"""
Implementación pura del algoritmo SM-2.
Sin efectos secundarios: calcula, el router persiste.
"""


def calcular_siguiente_repaso(
    calificacion: int,
    intervalo_actual: int,
    repeticiones: int,
    factor_facilidad: float,
) -> tuple[int, int, float]:
    """
    Retorna (nuevo_intervalo_dias, nuevas_repeticiones, nuevo_ef).
    Calificaciones: 0=nada, 1=muy difícil, 2=difícil, 3=bien, 4=fácil, 5=perfecto.
    """
    ef = factor_facilidad + (0.1 - (5 - calificacion) * (0.08 + (5 - calificacion) * 0.02))
    ef = max(1.3, ef)

    if calificacion < 3:
        return 1, 0, ef

    if repeticiones == 0:
        nuevo_intervalo = 1
    elif repeticiones == 1:
        nuevo_intervalo = 6
    else:
        nuevo_intervalo = round(intervalo_actual * ef)

    return nuevo_intervalo, repeticiones + 1, ef

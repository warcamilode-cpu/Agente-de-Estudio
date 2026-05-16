"""Tests del algoritmo SM-2."""
import pytest
from services.srs_engine import calcular_siguiente_repaso


def test_calificacion_menor_a_3_reinicia():
    """Calificación < 3 siempre retorna intervalo=1 y repeticiones=0."""
    for cal in (0, 1, 2):
        intervalo, reps, ef = calcular_siguiente_repaso(cal, 10, 5, 2.5)
        assert intervalo == 1
        assert reps == 0


def test_primera_repeticion_correcta():
    intervalo, reps, ef = calcular_siguiente_repaso(4, 1, 0, 2.5)
    assert intervalo == 1
    assert reps == 1


def test_segunda_repeticion_correcta():
    intervalo, reps, ef = calcular_siguiente_repaso(4, 1, 1, 2.5)
    assert intervalo == 6
    assert reps == 2


def test_repeticiones_posteriores_usan_ef():
    intervalo, reps, ef = calcular_siguiente_repaso(4, 6, 2, 2.5)
    assert intervalo == round(6 * 2.5)
    assert reps == 3


def test_ef_no_baja_de_1_3():
    _, _, ef = calcular_siguiente_repaso(0, 1, 0, 1.3)
    assert ef >= 1.3


def test_ef_sube_con_calificacion_perfecta():
    _, _, ef_antes = calcular_siguiente_repaso(3, 1, 0, 2.5)
    _, _, ef_perf  = calcular_siguiente_repaso(5, 1, 0, 2.5)
    assert ef_perf > ef_antes


def test_calificacion_3_es_correcta():
    intervalo, reps, ef = calcular_siguiente_repaso(3, 1, 0, 2.5)
    assert intervalo == 1
    assert reps == 1


def test_calificacion_5_maxima():
    intervalo, reps, ef = calcular_siguiente_repaso(5, 6, 2, 2.5)
    assert intervalo > 0
    assert ef > 2.5

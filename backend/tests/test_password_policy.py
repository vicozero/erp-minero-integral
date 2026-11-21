from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.identity.schemas import (
    PASSWORD_MIN_LENGTH,
    ChangePasswordIn,
    UserCreateIn,
    validate_password_policy,
)

_VALID = "Abc1!x"  # 6 caracteres con los cuatro tipos de carácter.


def test_el_minimo_de_la_politica_es_seis_caracteres() -> None:
    assert PASSWORD_MIN_LENGTH == 6
    assert validate_password_policy(_VALID) == _VALID


@pytest.mark.parametrize("password", ["Abc1!", "A1!bc"])
def test_la_politica_rechaza_menos_de_seis_caracteres(password: str) -> None:
    with pytest.raises(ValueError, match="al menos 6 caracteres"):
        validate_password_policy(password)


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("abc1!x", "letra mayúscula"),
        ("ABC1!X", "letra minúscula"),
        ("Abc!de", "número"),
        ("Abc12x", "carácter especial"),
    ],
)
def test_la_politica_exige_los_cuatro_tipos_de_caracter(password: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_password_policy(password)


def test_cambio_de_contrasena_acepta_seis_caracteres() -> None:
    payload = ChangePasswordIn(current_password="temporal", new_password=_VALID)
    assert payload.new_password == _VALID


def test_cambio_de_contrasena_rechaza_cinco_caracteres() -> None:
    with pytest.raises(ValidationError):
        ChangePasswordIn(current_password="temporal", new_password="Abc1!")


def test_alta_de_usuario_acepta_seis_caracteres() -> None:
    payload = UserCreateIn(
        username="politica.seis",
        email="politica.seis@example.invalid",
        full_name="Prueba Política Seis",
        password=_VALID,
    )
    assert payload.password == _VALID

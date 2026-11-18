from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.orm import Session

from app.db.seed import seed_demo_data
from app.modules.organization.models import Company
from app.shared.numbering import next_document_number
from sqlalchemy import select


@pytest.mark.skip(
    reason=(
        "Requiere PostgreSQL local con dos sesiones simultáneas. "
        "El arnés disponible usa SQLite en memoria y no puede validar FOR UPDATE."
    )
)
def test_folios_concurrentes_son_unicos(engine):
    """Verifica que la numeración con bloqueo de fila no duplique folios."""
    setup = Session(engine, autoflush=False, expire_on_commit=False, future=True)
    try:
        seed_demo_data(setup)
        company_id = setup.execute(select(Company.id).limit(1)).scalar_one()
    finally:
        setup.close()

    def issue_number(_: int) -> str:
        with Session(engine, autoflush=False, expire_on_commit=False, future=True) as session:
            _registry, number = next_document_number(
                session, "REQ", company_id, series="LAG"
            )
            session.commit()
            return number

    with ThreadPoolExecutor(max_workers=2) as pool:
        numbers = list(pool.map(issue_number, range(2)))

    assert numbers[0] != numbers[1]

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.documentation.models import DocumentEvent, DocumentNumbering, DocumentRegistry, DocumentType
from app.modules.organization.models import Company
from app.shared.numbering import next_document_number


def test_folios_concurrentes_son_unicos(engine) -> None:
    """La numeración con FOR UPDATE no duplica folios entre transacciones reales."""
    setup = Session(engine, autoflush=False, expire_on_commit=False, future=True)
    company = Company(code=f"CC-{uuid.uuid4().hex[:10]}", name="Compañía sintética concurrente")
    document_type = DocumentType(
        code=f"CC{uuid.uuid4().hex[:8]}", name="Documento sintético concurrente"
    )
    document_type_id: uuid.UUID | None = None

    try:
        setup.add_all([company, document_type])
        setup.flush()
        company_id = company.id
        document_type_id = document_type.id
        setup.commit()

        code = document_type.code

        def issue_number(_: int) -> tuple[str, uuid.UUID]:
            with Session(engine, autoflush=False, expire_on_commit=False, future=True) as session:
                registry, number = next_document_number(
                    session, code, company_id, series=f"S{uuid.uuid4().hex[:4].upper()}"
                )
                session.commit()
                return number, registry.id

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(issue_number, range(2)))

        assert results[0][0] != results[1][0]
    finally:
        cleanup = Session(engine, autoflush=False, expire_on_commit=False, future=True)
        try:
            numbering_ids = list(
                cleanup.execute(
                    select(DocumentNumbering.id).where(DocumentNumbering.company_id == company.id)
                ).scalars()
            )
            registry_ids = {result[1] for result in results} if "results" in locals() else set()
            if numbering_ids:
                registry_ids.update(
                    cleanup.execute(
                        select(DocumentRegistry.id).where(
                            DocumentRegistry.numbering_id.in_(numbering_ids)
                        )
                    ).scalars()
                )
            if registry_ids:
                cleanup.execute(
                    delete(DocumentEvent).where(DocumentEvent.document_registry_id.in_(registry_ids))
                )
                cleanup.execute(delete(DocumentRegistry).where(DocumentRegistry.id.in_(registry_ids)))
            if numbering_ids:
                cleanup.execute(delete(DocumentNumbering).where(DocumentNumbering.id.in_(numbering_ids)))
            if document_type_id is not None:
                cleanup.execute(delete(DocumentType).where(DocumentType.id == document_type_id))
            cleanup.execute(delete(Company).where(Company.id == company.id))
            cleanup.commit()
        finally:
            cleanup.close()
            setup.close()

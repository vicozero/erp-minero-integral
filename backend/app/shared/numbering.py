from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.documentation.models import DocumentEvent, DocumentNumbering, DocumentRegistry, DocumentType


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def _get_or_create_type(db: Session, code: str) -> DocumentType:
    doc_type = db.execute(select(DocumentType).where(DocumentType.code == code)).scalar_one_or_none()
    if doc_type is None:
        doc_type = DocumentType(code=code, name=code)
        db.add(doc_type)
        db.flush()
    return doc_type


def _get_or_create_numbering(
    db: Session,
    doc_type: DocumentType,
    company_id: uuid.UUID,
    mining_unit_id: uuid.UUID | None,
    series: str,
    year: int,
) -> DocumentNumbering:
    stmt = select(DocumentNumbering).where(
        DocumentNumbering.document_type_id == doc_type.id,
        DocumentNumbering.company_id == company_id,
        DocumentNumbering.mining_unit_id.is_(mining_unit_id) if mining_unit_id is None
        else DocumentNumbering.mining_unit_id == mining_unit_id,
        DocumentNumbering.series == series,
        DocumentNumbering.year == year,
    )
    numbering = db.execute(stmt.with_for_update()).scalar_one_or_none()
    if numbering is not None:
        return numbering
    try:
        with db.begin_nested():
            numbering = DocumentNumbering(
                document_type_id=doc_type.id,
                company_id=company_id,
                mining_unit_id=mining_unit_id,
                series=series,
                year=year,
                next_number=1,
            )
            db.add(numbering)
            db.flush()
    except IntegrityError:
        numbering = db.execute(stmt.with_for_update()).scalar_one()
    return db.execute(stmt.with_for_update()).scalar_one()


def next_document_number(
    db: Session,
    document_type_code: str,
    company_id: uuid.UUID,
    *,
    series: str = "GEN",
    mining_unit_id: uuid.UUID | None = None,
) -> tuple[DocumentRegistry, str]:
    year = _current_year()
    doc_type = _get_or_create_type(db, document_type_code)
    numbering = _get_or_create_numbering(db, doc_type, company_id, mining_unit_id, series, year)

    number = numbering.next_number
    numbering.next_number = number + 1
    full_number = f"{document_type_code}-{series}-{year}-{number:06d}"

    registry = DocumentRegistry(
        document_type_id=doc_type.id,
        numbering_id=numbering.id,
        full_number=full_number,
        entity_type="PENDING",
        status="ISSUED",
    )
    db.add(registry)
    db.flush()
    record_document_event(db, registry, "DOCUMENT_NUMBER_ISSUED", None, "ISSUED", None)
    return registry, full_number


def attach_entity(db: Session, registry: DocumentRegistry, entity_type: str, entity_id: uuid.UUID) -> None:
    registry.entity_type = entity_type
    registry.entity_id = entity_id


def record_document_event(
    db: Session,
    registry: DocumentRegistry,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    actor_id: uuid.UUID | None,
    metadata: dict | None = None,
) -> DocumentEvent:
    event = DocumentEvent(
        document_registry_id=registry.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event

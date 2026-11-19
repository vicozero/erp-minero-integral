from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DocumentTemplate

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
VA_TEMPLATE_SHA = "82c868df58f06ed7df029c8a67e8239b6f73df92e95f0c8bae8b04cc8a5f6e2e"
REQ_TEMPLATE_SHA = "5df7f95ee6d850f2b067708a40ad6ea4551c47a7dd2578a3519bde4800526062"


@dataclass(frozen=True)
class TemplateSpec:
    code: str
    document_type_code: str
    template_version: int
    description: str
    page_width_pt: Decimal
    page_height_pt: Decimal
    orientation: str
    source_sha256: str
    logo_name: str


VA_SPEC = TemplateSpec(
    code="VA_SALIDA_ALMACEN",
    document_type_code="VA",
    template_version=1,
    description="Vale de salida de almacén, carta apaisada, 10 partidas por hoja",
    page_width_pt=Decimal("792.00"),
    page_height_pt=Decimal("612.00"),
    orientation="LANDSCAPE",
    source_sha256=VA_TEMPLATE_SHA,
    logo_name="logo_va.png",
)

REQ_SPEC = TemplateSpec(
    code="REQ_COMPRA",
    document_type_code="REQ",
    template_version=1,
    description="Requisición de compra, carta vertical, 21 partidas por hoja",
    page_width_pt=Decimal("612.00"),
    page_height_pt=Decimal("792.00"),
    orientation="PORTRAIT",
    source_sha256=REQ_TEMPLATE_SHA,
    logo_name="logo_req.png",
)

SPECS = {VA_SPEC.code: VA_SPEC, REQ_SPEC.code: REQ_SPEC}


def ensure_template(db: Session, spec: TemplateSpec) -> DocumentTemplate:
    tpl = db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.code == spec.code,
            DocumentTemplate.template_version == spec.template_version,
        )
    ).scalar_one_or_none()
    if tpl is not None:
        return tpl
    tpl = DocumentTemplate(
        code=spec.code,
        document_type_code=spec.document_type_code,
        template_version=spec.template_version,
        description=spec.description,
        page_width_pt=spec.page_width_pt,
        page_height_pt=spec.page_height_pt,
        orientation=spec.orientation,
        source_sha256=spec.source_sha256,
        is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def asset_bytes(name: str) -> bytes:
    return (ASSETS_DIR / name).read_bytes()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

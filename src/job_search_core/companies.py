"""Application service for confirmed normalized Company updates."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from job_search_core.models import Company
from job_search_core.schemas import CompanyWebsiteUpdate


class CompanyNotFoundError(Exception):
    """Signal that a requested Company does not exist."""


def set_company_website(
    session: Session, company_id: uuid.UUID, request: CompanyWebsiteUpdate
) -> Company:
    """Idempotently set the explicitly confirmed official Company website."""
    company = session.get(Company, company_id)
    if company is None:
        raise CompanyNotFoundError
    company.website_url = str(request.website_url)
    session.flush()
    return company

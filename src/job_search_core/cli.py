"""Machine-facing JSON CLI for Core platform and Vacancy operations."""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date

import uvicorn

from job_search_core.app import component_info
from job_search_core.applications import (
    ApplicationAlreadyExistsError,
    ApplicationIdempotencyConflictError,
    ApplicationVacancyNotFoundError,
    create_application,
    list_applications,
)
from job_search_core.assessments import (
    AssessmentAlreadyExistsError,
    AssessmentIdempotencyConflictError,
    AssessmentVacancyNotFoundError,
    create_assessment,
    list_assessments,
)
from job_search_core.config import Settings
from job_search_core.database import Database
from job_search_core.hypotheses import (
    HypothesisAlreadyClosedError,
    HypothesisAlreadyExistsError,
    HypothesisIdempotencyConflictError,
    HypothesisNotFoundError,
    close_hypothesis,
    create_hypothesis,
    list_hypotheses,
)
from job_search_core.metrics import (
    DailyMetricNotFoundError,
    EmptyDailyMetricUpdateError,
    MetricIdempotencyConflictError,
    get_daily_metric,
    list_daily_metrics,
    set_daily_metric,
)
from job_search_core.models import HypothesisStatus, PersonStatus
from job_search_core.people import (
    PersonAlreadyExistsError,
    PersonCompanyMismatchError,
    PersonCompanyNotFoundError,
    PersonIdempotencyConflictError,
    PersonNotFoundError,
    PersonVacancyNotFoundError,
    create_person,
    list_people,
    update_person_status,
)
from job_search_core.schemas import (
    ApplicationCreate,
    ApplicationRead,
    AssessmentCreate,
    AssessmentRead,
    DailyMetricRead,
    DailyMetricUpdate,
    HypothesisCreate,
    HypothesisRead,
    PersonCreate,
    PersonRead,
    VacancyCreate,
    VacancyRead,
)
from job_search_core.vacancies import (
    IdempotencyConflictError,
    VacancyAlreadyExistsError,
    create_vacancy,
    list_vacancies,
)


@dataclass(frozen=True)
class Envelope:
    """Versioned JSON envelope written as the CLI's only stdout document."""

    contract_version: str
    command: str
    ok: bool
    data: object
    errors: list[dict[str, str]]
    trace_id: str


def envelope(command: str, *, data: object, errors: list[dict[str, str]] | None = None) -> Envelope:
    """Build a contract-v1 response with one correlation identifier."""
    failures = errors or []
    return Envelope(
        contract_version="1.0",
        command=command,
        ok=not failures,
        data=data,
        errors=failures,
        trace_id=str(uuid.uuid4()),
    )


def build_parser() -> argparse.ArgumentParser:
    """Define stable commands while keeping human help separate from JSON output."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("info", help="print versioned component metadata as JSON")
    subparsers.add_parser("serve", help="run the Core HTTP development server")

    vacancy = subparsers.add_parser("vacancy", help="manage normalized vacancies")
    vacancy_commands = vacancy.add_subparsers(dest="vacancy_command", required=True)
    create = vacancy_commands.add_parser("create", help="idempotently create a vacancy")
    create.add_argument("--idempotency-key", required=True)
    create.add_argument("--source", required=True)
    create.add_argument("--external-id", required=True)
    create.add_argument("--company-name", required=True)
    create.add_argument("--company-external-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--url", required=True)
    create.add_argument("--description")
    vacancy_commands.add_parser("list", help="list persisted vacancies")

    application = subparsers.add_parser("application", help="manage normalized applications")
    application_commands = application.add_subparsers(dest="application_command", required=True)
    application_create = application_commands.add_parser(
        "create", help="idempotently create an application"
    )
    application_create.add_argument("--idempotency-key", required=True)
    application_create.add_argument("--vacancy-id", required=True)
    application_create.add_argument("--source", required=True)
    application_create.add_argument("--external-id", required=True)
    application_create.add_argument("--applied-at")
    application_create.add_argument("--resume-version")
    application_create.add_argument("--cover-letter-version")
    application_create.add_argument("--cover-letter-text")
    application_create.add_argument("--result")
    application_create.add_argument("--next-action")
    application_create.add_argument("--next-action-at")
    application_commands.add_parser("list", help="list persisted applications")

    metric = subparsers.add_parser("metric", help="manage normalized daily metrics")
    metric_commands = metric.add_subparsers(dest="metric_command", required=True)
    metric_set = metric_commands.add_parser("set", help="idempotently apply a daily snapshot")
    metric_set.add_argument("--idempotency-key", required=True)
    metric_set.add_argument("--date", required=True)
    for field in (
        "views-total",
        "views-new",
        "applications",
        "replies",
        "invitations",
        "rejections",
    ):
        metric_set.add_argument(f"--{field}", type=int)
    metric_set.add_argument("--notes")
    metric_show = metric_commands.add_parser("show", help="show one daily snapshot")
    metric_show.add_argument("--date", required=True)
    metric_list = metric_commands.add_parser("list", help="list daily snapshots")
    metric_list.add_argument("--since")
    metric_list.add_argument("--limit", type=int, default=60)

    person = subparsers.add_parser("person", help="manage confirmed professional contacts")
    person_commands = person.add_subparsers(dest="person_command", required=True)
    person_create = person_commands.add_parser("create", help="idempotently create a Person")
    person_create.add_argument("--idempotency-key", required=True)
    person_create.add_argument("--company-id", required=True)
    person_create.add_argument("--vacancy-id")
    person_create.add_argument("--source", required=True)
    person_create.add_argument("--external-id", required=True)
    person_create.add_argument("--full-name", required=True)
    person_create.add_argument("--role", required=True)
    person_create.add_argument("--title")
    person_create.add_argument("--url")
    person_create.add_argument("--confidence", type=float)
    person_create.add_argument("--notes")
    person_commands.add_parser("list", help="list confirmed contacts")
    person_status = person_commands.add_parser("set-status", help="change contact status")
    person_status.add_argument("--person-id", required=True)
    person_status.add_argument("--status", required=True)

    hypothesis = subparsers.add_parser("hypothesis", help="manage search experiments")
    hypothesis_commands = hypothesis.add_subparsers(dest="hypothesis_command", required=True)
    hypothesis_create = hypothesis_commands.add_parser(
        "create", help="idempotently create an active hypothesis"
    )
    hypothesis_create.add_argument("--idempotency-key", required=True)
    hypothesis_create.add_argument("--source", required=True)
    hypothesis_create.add_argument("--external-id", required=True)
    hypothesis_create.add_argument("--title", required=True)
    hypothesis_create.add_argument("--description")
    hypothesis_create.add_argument("--test-size", type=int)
    hypothesis_create.add_argument("--metric")
    hypothesis_list = hypothesis_commands.add_parser("list", help="list hypotheses")
    hypothesis_list.add_argument("--status", choices=[item.value for item in HypothesisStatus])
    hypothesis_close = hypothesis_commands.add_parser(
        "close", help="close an active hypothesis with an observed result"
    )
    hypothesis_close.add_argument("--hypothesis-id", required=True)
    hypothesis_close.add_argument("--result", required=True)
    assessment = subparsers.add_parser("assessment", help="manage normalized scoring results")
    assessment_commands = assessment.add_subparsers(dest="assessment_command", required=True)
    assessment_create = assessment_commands.add_parser(
        "create", help="idempotently create an assessment"
    )
    for name in (
        "idempotency-key",
        "vacancy-id",
        "source",
        "external-id",
        "relevance-score",
        "verdict",
        "reason",
        "action",
        "model",
        "prompt-version",
        "assessed-at",
    ):
        assessment_create.add_argument(f"--{name}", required=True)
    assessment_create.add_argument("--risk")
    assessment_list = assessment_commands.add_parser("list", help="list assessments")
    assessment_list.add_argument("--vacancy-id")
    return parser


def info_payload() -> Envelope:
    """Build the version-1 JSON response for automation and host integrations."""
    health = component_info()
    return envelope(
        "info",
        data={"component": health.component, "status": health.status, "version": health.version},
    )


def vacancy_payload(args: argparse.Namespace, database: Database) -> tuple[Envelope, int]:
    """Execute one transactional vacancy subcommand and return its JSON result."""
    if args.vacancy_command == "list":
        with database.session() as session:
            items = [
                VacancyRead.model_validate(item).model_dump(mode="json")
                for item in list_vacancies(session)
            ]
        return envelope("vacancy.list", data={"items": items, "total": len(items)}), 0

    request = VacancyCreate(
        company_name=args.company_name,
        company_external_id=args.company_external_id,
        source=args.source,
        external_id=args.external_id,
        title=args.title,
        url=args.url,
        description=args.description,
    )
    try:
        with database.session() as session:
            result = create_vacancy(session, request, args.idempotency_key)
            data = VacancyRead.model_validate(result.vacancy).model_dump(mode="json")
            data["created"] = result.created
    except IdempotencyConflictError:
        error = {"code": "idempotency_conflict", "message": "key used for different request"}
        return envelope("vacancy.create", data={}, errors=[error]), 1
    except VacancyAlreadyExistsError:
        error = {"code": "vacancy_exists", "message": "source vacancy already exists"}
        return envelope("vacancy.create", data={}, errors=[error]), 1
    return envelope("vacancy.create", data=data), 0


def application_payload(args: argparse.Namespace, database: Database) -> tuple[Envelope, int]:
    """Execute one transactional Application subcommand and return JSON output."""
    if args.application_command == "list":
        with database.session() as session:
            items = [
                ApplicationRead.model_validate(item).model_dump(mode="json")
                for item in list_applications(session)
            ]
        return envelope("application.list", data={"items": items, "total": len(items)}), 0

    request = ApplicationCreate(
        vacancy_id=args.vacancy_id,
        source=args.source,
        external_id=args.external_id,
        applied_at=args.applied_at,
        resume_version=args.resume_version,
        cover_letter_version=args.cover_letter_version,
        cover_letter_text=args.cover_letter_text,
        result=args.result,
        next_action=args.next_action,
        next_action_at=args.next_action_at,
    )
    try:
        with database.session() as session:
            result = create_application(session, request, args.idempotency_key)
            data = ApplicationRead.model_validate(result.application).model_dump(mode="json")
            data["created"] = result.created
    except ApplicationIdempotencyConflictError:
        error = {"code": "idempotency_conflict", "message": "key used for different request"}
        return envelope("application.create", data={}, errors=[error]), 1
    except ApplicationAlreadyExistsError:
        error = {"code": "application_exists", "message": "source application already exists"}
        return envelope("application.create", data={}, errors=[error]), 1
    except ApplicationVacancyNotFoundError:
        error = {"code": "vacancy_not_found", "message": "vacancy does not exist"}
        return envelope("application.create", data={}, errors=[error]), 1
    return envelope("application.create", data=data), 0


def metric_payload(args: argparse.Namespace, database: Database) -> tuple[Envelope, int]:
    """Execute one transactional Daily Metric command and return JSON output."""
    if args.metric_command == "list":
        since = date.fromisoformat(args.since) if args.since else None
        with database.session() as session:
            items = [
                DailyMetricRead.model_validate(item).model_dump(mode="json")
                for item in list_daily_metrics(session, since=since, limit=args.limit)
            ]
        return envelope("metric.list", data={"items": items, "total": len(items)}), 0
    metric_date = date.fromisoformat(args.date)
    if args.metric_command == "show":
        try:
            with database.session() as session:
                data = DailyMetricRead.model_validate(
                    get_daily_metric(session, metric_date)
                ).model_dump(mode="json")
        except DailyMetricNotFoundError:
            error = {"code": "metric_not_found", "message": "daily metric does not exist"}
            return envelope("metric.show", data={}, errors=[error]), 1
        return envelope("metric.show", data=data), 0

    values = {
        field: getattr(args, field)
        for field in (
            "views_total",
            "views_new",
            "applications",
            "replies",
            "invitations",
            "rejections",
            "notes",
        )
        if getattr(args, field) is not None
    }
    request = DailyMetricUpdate.model_validate(values)
    try:
        with database.session() as session:
            result = set_daily_metric(session, metric_date, request, args.idempotency_key)
            data = DailyMetricRead.model_validate(result.metric).model_dump(mode="json")
            data["created"] = result.created
    except EmptyDailyMetricUpdateError:
        error = {"code": "empty_metric_update", "message": "at least one field is required"}
        return envelope("metric.set", data={}, errors=[error]), 1
    except MetricIdempotencyConflictError:
        error = {"code": "idempotency_conflict", "message": "key used for different request"}
        return envelope("metric.set", data={}, errors=[error]), 1
    return envelope("metric.set", data=data), 0


def person_payload(args: argparse.Namespace, database: Database) -> tuple[Envelope, int]:
    """Execute one transactional Person command and return JSON output."""
    if args.person_command == "list":
        with database.session() as session:
            items = [
                PersonRead.model_validate(item).model_dump(mode="json")
                for item in list_people(session)
            ]
        return envelope("person.list", data={"items": items, "total": len(items)}), 0
    if args.person_command == "set-status":
        try:
            with database.session() as session:
                data = PersonRead.model_validate(
                    update_person_status(
                        session, uuid.UUID(args.person_id), PersonStatus(args.status)
                    )
                ).model_dump(mode="json")
        except PersonNotFoundError:
            error = {"code": "person_not_found", "message": "person does not exist"}
            return envelope("person.set-status", data={}, errors=[error]), 1
        return envelope("person.set-status", data=data), 0
    request = PersonCreate(
        company_id=args.company_id,
        vacancy_id=args.vacancy_id,
        source=args.source,
        external_id=args.external_id,
        full_name=args.full_name,
        role=args.role,
        title=args.title,
        url=args.url,
        confidence=args.confidence,
        notes=args.notes,
    )
    try:
        with database.session() as session:
            result = create_person(session, request, args.idempotency_key)
            data = PersonRead.model_validate(result.person).model_dump(mode="json")
            data["created"] = result.created
    except PersonIdempotencyConflictError:
        error = {"code": "idempotency_conflict", "message": "key used for different request"}
        return envelope("person.create", data={}, errors=[error]), 1
    except PersonAlreadyExistsError:
        error = {"code": "person_exists", "message": "source Person already exists"}
        return envelope("person.create", data={}, errors=[error]), 1
    except PersonCompanyNotFoundError:
        error = {"code": "company_not_found", "message": "company does not exist"}
        return envelope("person.create", data={}, errors=[error]), 1
    except PersonVacancyNotFoundError:
        error = {"code": "vacancy_not_found", "message": "vacancy does not exist"}
        return envelope("person.create", data={}, errors=[error]), 1
    except PersonCompanyMismatchError:
        error = {"code": "person_company_mismatch", "message": "vacancy company differs"}
        return envelope("person.create", data={}, errors=[error]), 1
    return envelope("person.create", data=data), 0


def hypothesis_payload(args: argparse.Namespace, database: Database) -> tuple[Envelope, int]:
    """Execute one transactional Hypothesis command and return JSON output."""
    if args.hypothesis_command == "list":
        status = HypothesisStatus(args.status) if args.status else None
        with database.session() as session:
            items = [
                HypothesisRead.model_validate(item).model_dump(mode="json")
                for item in list_hypotheses(session, status)
            ]
        return envelope("hypothesis.list", data={"items": items, "total": len(items)}), 0
    if args.hypothesis_command == "close":
        try:
            with database.session() as session:
                data = HypothesisRead.model_validate(
                    close_hypothesis(session, uuid.UUID(args.hypothesis_id), args.result)
                ).model_dump(mode="json")
        except HypothesisNotFoundError:
            error = {"code": "hypothesis_not_found", "message": "hypothesis does not exist"}
            return envelope("hypothesis.close", data={}, errors=[error]), 1
        except HypothesisAlreadyClosedError:
            error = {
                "code": "hypothesis_already_closed",
                "message": "closed result cannot be replaced",
            }
            return envelope("hypothesis.close", data={}, errors=[error]), 1
        return envelope("hypothesis.close", data=data), 0
    request = HypothesisCreate(
        source=args.source,
        external_id=args.external_id,
        title=args.title,
        description=args.description,
        test_size=args.test_size,
        metric=args.metric,
    )
    try:
        with database.session() as session:
            result = create_hypothesis(session, request, args.idempotency_key)
            data = HypothesisRead.model_validate(result.hypothesis).model_dump(mode="json")
            data["created"] = result.created
    except HypothesisIdempotencyConflictError:
        error = {"code": "idempotency_conflict", "message": "key used for different request"}
        return envelope("hypothesis.create", data={}, errors=[error]), 1
    except HypothesisAlreadyExistsError:
        error = {"code": "hypothesis_exists", "message": "source hypothesis exists"}
        return envelope("hypothesis.create", data={}, errors=[error]), 1
    return envelope("hypothesis.create", data=data), 0


def assessment_payload(args: argparse.Namespace, database: Database) -> tuple[Envelope, int]:
    """Execute one normalized Assessment command and return JSON output."""
    if args.assessment_command == "list":
        vacancy_id = uuid.UUID(args.vacancy_id) if args.vacancy_id else None
        with database.session() as session:
            items = [
                AssessmentRead.model_validate(item).model_dump(mode="json")
                for item in list_assessments(session, vacancy_id)
            ]
        return envelope("assessment.list", data={"items": items, "total": len(items)}), 0
    request = AssessmentCreate(
        vacancy_id=args.vacancy_id,
        source=args.source,
        external_id=args.external_id,
        relevance_score=int(args.relevance_score),
        verdict=args.verdict,
        reason=args.reason,
        risk=args.risk,
        action=args.action,
        model=args.model,
        prompt_version=args.prompt_version,
        assessed_at=args.assessed_at,
    )
    try:
        with database.session() as session:
            result = create_assessment(session, request, args.idempotency_key)
            data = AssessmentRead.model_validate(result.assessment).model_dump(mode="json")
            data["created"] = result.created
    except AssessmentIdempotencyConflictError:
        return envelope(
            "assessment.create",
            data={},
            errors=[{"code": "idempotency_conflict", "message": "key used for different request"}],
        ), 1
    except AssessmentAlreadyExistsError:
        return envelope(
            "assessment.create",
            data={},
            errors=[{"code": "assessment_exists", "message": "source assessment exists"}],
        ), 1
    except AssessmentVacancyNotFoundError:
        return envelope(
            "assessment.create",
            data={},
            errors=[{"code": "vacancy_not_found", "message": "vacancy does not exist"}],
        ), 1
    return envelope("assessment.create", data=data), 0


def emit(payload: Envelope) -> None:
    """Write exactly one deterministic JSON document to standard output."""
    print(json.dumps(asdict(payload), ensure_ascii=False, sort_keys=True))


def main(argv: Sequence[str] | None = None, *, database: Database | None = None) -> int:
    """Execute one CLI command and return a process-compatible exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "info":
        emit(info_payload())
        return 0
    settings = Settings()
    if args.command == "vacancy":
        payload, exit_code = vacancy_payload(args, database or Database(settings.database_url))
        emit(payload)
        return exit_code
    if args.command == "application":
        payload, exit_code = application_payload(args, database or Database(settings.database_url))
        emit(payload)
        return exit_code
    if args.command == "metric":
        payload, exit_code = metric_payload(args, database or Database(settings.database_url))
        emit(payload)
        return exit_code
    if args.command == "person":
        payload, exit_code = person_payload(args, database or Database(settings.database_url))
        emit(payload)
        return exit_code
    if args.command == "hypothesis":
        payload, exit_code = hypothesis_payload(args, database or Database(settings.database_url))
        emit(payload)
        return exit_code
    if args.command == "assessment":
        payload, exit_code = assessment_payload(args, database or Database(settings.database_url))
        emit(payload)
        return exit_code

    uvicorn.run(
        "job_search_core.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

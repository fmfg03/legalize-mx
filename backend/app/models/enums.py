from __future__ import annotations

from enum import StrEnum


class ExpedienteStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    STAYED = "stayed"
    CLOSED = "closed"
    ARCHIVED = "archived"


class PartyRole(StrEnum):
    ACTOR = "actor"
    DEMANDADO = "demandado"
    QUEJOSO = "quejoso"
    AUTORIDAD_RESPONSABLE = "autoridad_responsable"
    TERCERO = "tercero"
    IMPUTADO = "imputado"
    VICTIMA = "victima"
    DEFENSOR = "defensor"
    APODERADO = "apoderado"
    OTHER = "other"


class DocumentType(StrEnum):
    NOTIFICACION = "notificacion"
    EMPLAZAMIENTO = "emplazamiento"
    ACUERDO = "acuerdo"
    SENTENCIA = "sentencia"
    DEMANDA = "demanda"
    ESCRITO = "escrito"
    OFICIO = "oficio"
    CONSTANCIA = "constancia"
    ANEXO = "anexo"
    PRUEBA = "prueba"
    OTRO = "otro"


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    VOID = "void"
    ARCHIVED = "archived"


class VersionSourceKind(StrEnum):
    GENERATED = "generated"
    UPLOADED = "uploaded"
    IMPORTED = "imported"
    OCR = "ocr"
    SYSTEM = "system"


class EventType(StrEnum):
    ACTUACION = "actuacion"
    NOTIFICACION = "notificacion"
    AUDIENCIA = "audiencia"
    PRESENTACION = "presentacion"
    RESOLUCION = "resolucion"
    OTHER = "other"


class DeadlineStatus(StrEnum):
    OPEN = "open"
    SATISFIED = "satisfied"
    MISSED = "missed"
    CANCELLED = "cancelled"


class ReleaseVerdict(StrEnum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    BYPASS = "bypass"


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    OBSERVER = "observer"

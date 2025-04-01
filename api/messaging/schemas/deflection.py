from __future__ import annotations

from dataclasses import dataclass

from appointments.schemas.v2.member_appointments import (
    MemberAppointmentsListServiceResponseElement,
)


@dataclass(frozen=True)
class DeflectionMemberContextResponseSchema:
    member_id: int | None = None
    active_track_ids: list[int] | None = None
    active_track_names: list[str] | None = None
    member_state: str | None = None
    is_doula_only_member: bool | None = None


@dataclass(frozen=True)
class DeflectionTrackCategoriesSchema:
    member_id: int
    need_categories: list[str]


@dataclass(frozen=True)
class DeflectionCategoryNeedsSchema:
    needs: list[str]


@dataclass(frozen=True)
class DeflectionUpcomingAppointmentsSchema:
    appointments: list[MemberAppointmentsListServiceResponseElement] | None = None


@dataclass(frozen=True)
class DeflectionCancelAppointmentRequestSchema:
    appointment_id: int
    member_id: int

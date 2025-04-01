from __future__ import annotations

import datetime

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain import model
from storage.repository import base

__all__ = (
    "UserExternalIdentityRepository",
    "IdentityProviderRepository",
    "IDPFieldAliasRepository",
)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class IdentityProviderRepository(base.BaseRepository[model.IdentityProvider]):  # type: ignore[type-var] # Type argument "IdentityProvider" of "BaseRepository" must be a subtype of "Instance"
    """A repository for managing external Identity Providers."""

    model = model.IdentityProvider

    @trace_wrapper
    def get_by_name(self, *, name: str) -> model | None:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.IdentityProviderRepository.model" is not valid as a type
        """Get an IdentityProvider by name."""

        where = self.table.c.name == name
        result = self.execute_select(where=where)
        entry = self.deserialize(result.first())
        return entry

    @trace_wrapper
    def get_all_by_time_range(
        self, *, end: datetime.date, start: datetime.date | None = None
    ) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.IdentityProviderRepository.model" is not valid as a type
        """Get a list of identity providers by the modified time range"""
        if start:
            where_clauses = [
                self.table.c.modified_at <= end,
                self.table.c.modified_at >= start,
            ]
        else:
            where_clauses = [
                self.table.c.modified_at <= end,
            ]
        result = self.execute_select(where=sa.and_(*where_clauses))
        rows = result.fetchall()
        return self.deserialize_list(rows=rows)  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.IdentityProviderRepository.model" is not valid as a type
        return dict(name=instance.name, metadata=instance.metadata)  # type: ignore[attr-defined] # model? has no attribute "name" #type: ignore[attr-defined] # model? has no attribute "metadata"

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column("name", sa.String, nullable=False),
            sa.Column("metadata", sa.Text, nullable=False),
        )


class IDPFieldAliasRepository(base.BaseRepository[model.IdentityProviderFieldAlias]):  # type: ignore[type-var] # Type argument "IdentityProviderFieldAlias" of "BaseRepository" must be a subtype of "Instance"
    """A repository for managing field mappings for IDP external identities."""

    model = model.IdentityProviderFieldAlias

    @trace_wrapper
    def get_by_idp_id(self, *, idp_id: int) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.IDPFieldAliasRepository.model" is not valid as a type
        """Get an IdentityProvider by name."""
        where = self.table.c.identity_provider_id == idp_id
        result = self.execute_select(where=where)
        entries = [self.deserialize(row) for row in result.fetchall()]
        return entries

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.IDPFieldAliasRepository.model" is not valid as a type
        return dict(
            field=instance.field,  # type: ignore[attr-defined] # model? has no attribute "field"
            alias=instance.alias,  # type: ignore[attr-defined] # model? has no attribute "alias"
            identity_provider_id=instance.identity_provider_id,  # type: ignore[attr-defined] # model? has no attribute "identity_provider_id"
        )

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column("field", sa.String, nullable=False),
            sa.Column("alias", sa.String, nullable=False),
            sa.Column("identity_provider_id", sa.BigInteger, nullable=False),
        )


class UserExternalIdentityRepository(base.BaseRepository[model.UserExternalIdentity]):  # type: ignore[type-var] # Type argument "UserExternalIdentity" of "BaseRepository" must be a subtype of "Instance"
    """A repository for managing externally-provided identities for users."""

    model = model.UserExternalIdentity

    @trace_wrapper
    def get_by_idp_id(self, *, idp_id: int) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        """Get all external identities associated to an IDP."""
        where = self.table.c.identity_provider_id == idp_id
        result = self.execute_select(where=where)
        entries = [self.deserialize(row) for row in result.fetchall()]
        return entries

    @trace_wrapper
    def get_by_idp_and_external_user_id(
        self, *, idp_id: int, external_user_id: str
    ) -> model | None:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        """Get all external identities associated to an IDP."""
        where = (self.table.c.identity_provider_id == idp_id) & (
            self.table.c.external_user_id == external_user_id
        )
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)

    @trace_wrapper
    def get_by_auth0_user_id(
        self, *, auth0_user_id: str
    ) -> model | None:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        """Get all external identities associated to an IDP."""
        where = self.table.c.auth0_user_id == auth0_user_id
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)

    @trace_wrapper
    def get_by_reporting_id(self, *, reporting_id: str) -> model | None:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        """Get an external identity by reporting ID.

        The reporting ID is unique across all identity providers.
        """
        if reporting_id is None:
            return

        where = self.table.c.reporting_id == reporting_id
        result = self.execute_select(where=where)
        entry = self.deserialize(result.first())
        return entry

    @trace_wrapper
    def get_by_user_id(self, *, user_id: int) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        """Get all external identities associated to a user ID."""

        where = self.table.c.user_id == user_id
        result = self.execute_select(where=where)
        entries = [self.deserialize(row) for row in result.fetchall()]
        return entries

    @trace_wrapper
    def get_all_by_time_range(
        self, *, end: datetime.date, start: datetime.date
    ) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        """Get a list of user external identities by the modified time range"""

        where_clauses = [
            self.table.c.modified_at <= end,
            self.table.c.modified_at >= start,
        ]
        result = self.execute_select(where=sa.and_(*where_clauses))
        rows = result.fetchall()
        return self.deserialize_list(rows=rows)  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.sso.UserExternalIdentityRepository.model" is not valid as a type
        return dict(
            user_id=instance.user_id,  # type: ignore[attr-defined] # model? has no attribute "user_id"
            identity_provider_id=instance.identity_provider_id,  # type: ignore[attr-defined] # model? has no attribute "identity_provider_id"
            external_user_id=instance.external_user_id,  # type: ignore[attr-defined] # model? has no attribute "external_user_id"
            external_organization_id=instance.external_organization_id,  # type: ignore[attr-defined] # model? has no attribute "external_organization_id"
            reporting_id=instance.reporting_id,  # type: ignore[attr-defined] # model? has no attribute "reporting_id"
            unique_corp_id=instance.unique_corp_id,  # type: ignore[attr-defined] # model? has no attribute "unique_corp_id"
            sso_email=instance.sso_email,  # type: ignore[attr-defined] # model? has no attribute "sso_email"
            auth0_user_id=instance.auth0_user_id,  # type: ignore[attr-defined] # model? has no attribute "auth0_user_id"
            sso_user_first_name=instance.sso_user_first_name,  # type: ignore[attr-defined] # model? has no attribute "sso_user_first_name"
            sso_user_last_name=instance.sso_user_last_name,  # type: ignore[attr-defined] # model? has no attribute "sso_user_last_name"
        )

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column("user_id", sa.Integer, nullable=False),
            sa.Column("identity_provider_id", sa.Integer, nullable=False),
            sa.Column("external_user_id", sa.String, nullable=False),
            sa.Column("external_organization_id", sa.String, nullable=False),
            sa.Column("reporting_id", sa.String, unique=True),
            sa.Column("unique_corp_id", sa.String),
            sa.Column("sso_email", sa.String),
            sa.Column("auth0_user_id", sa.String),
            sa.Column("sso_user_first_name", sa.String),
            sa.Column("sso_user_last_name", sa.String),
        )

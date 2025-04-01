from __future__ import annotations

import datetime
from collections import defaultdict
from traceback import format_exc
from typing import Dict, List, Optional

import ddtrace.ext
import sqlalchemy.orm
from sqlalchemy.dialects.mysql import Insert
from sqlalchemy.exc import IntegrityError, OperationalError

from storage import connection
from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    WalletState,
)
from wallet.models.models import AllowedCategoryAccessLevel
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingsAllowedCategoryRule,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWallet,
    ReimbursementWalletAllowedCategorySettings,
    ReimbursementWalletCategoryRuleEvaluationFailure,
    ReimbursementWalletCategoryRuleEvaluationResult,
)
from wallet.services.reimbursement_category_activation_constants import (
    SYSTEM_USER,
    TENURE_RULES,
)

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class CategoryActivationRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession | None = None):
        self.session = session or connection.db.session

    @trace_wrapper
    def get_all_allowed_category_ids_that_have_rules(self) -> List[int]:
        """
        Returns a list of category IDs that have associated allowed category rules.
        """
        sql = """
                SELECT DISTINCT allowed_category.id AS category_id
                FROM reimbursement_organization_settings_allowed_category allowed_category
                JOIN reimbursement_organization_settings_allowed_category_rule rule
                ON allowed_category.id = rule.reimbursement_organization_settings_allowed_category_id;
                """
        result = self.session.execute(sql).fetchall()
        return [row["category_id"] for row in result]

    @trace_wrapper
    def get_all_allowed_category_ids_without_rules(self) -> List[int]:
        """
        Return a list of all allowed category IDs that do not have allowed category rules.
        """
        sql = """
           SELECT allowed_category.id AS category_id
           FROM reimbursement_organization_settings_allowed_category allowed_category
           LEFT JOIN reimbursement_organization_settings_allowed_category_rule rule
           ON allowed_category.id = rule.reimbursement_organization_settings_allowed_category_id
           WHERE rule.id IS NULL;
           """
        result = self.session.execute(sql).fetchall()
        return [row["category_id"] for row in result]

    @trace_wrapper
    def get_all_wallets_from_allowed_categories(
        self, allowed_category_ids: List[int]
    ) -> Dict[int, List[ReimbursementWallet]]:
        """
        Returns a dictionary of all the qualified wallets for a given allowed category id
        """
        query = """
                SELECT
                    reimbursement_organization_settings_allowed_category.id AS category_id,
                    reimbursement_wallet.*
                FROM
                    reimbursement_wallet
                JOIN
                    reimbursement_organization_settings ON reimbursement_wallet.reimbursement_organization_settings_id = reimbursement_organization_settings.id
                JOIN
                    reimbursement_organization_settings_allowed_category ON reimbursement_organization_settings.id = reimbursement_organization_settings_allowed_category.reimbursement_organization_settings_id
                WHERE
                    reimbursement_wallet.state = :qualified_wallet
                AND
                    reimbursement_organization_settings_allowed_category.id IN :allowed_category_ids
            """
        result = self.session.execute(
            query,
            {
                "allowed_category_ids": allowed_category_ids,
                "qualified_wallet": WalletState.QUALIFIED,
            },
        )

        rows = result.fetchall()

        # Extract wallet IDS
        wallet_ids = [row["id"] for row in rows]
        wallets = self.get_all_wallets_by_ids(wallet_ids=wallet_ids)

        # Create a map of wallet IDS to object
        wallet_map = {wallet.id: wallet for wallet in wallets}

        # Create the final mapping of category ID to wallet objects
        category_wallets_map = defaultdict(list)
        for row in rows:
            category_id = row["category_id"]
            wallet = wallet_map.get(row["id"])
            if wallet:
                category_wallets_map[category_id].append(wallet)
        return category_wallets_map

    @trace_wrapper
    def get_all_category_rules_for_allowed_categories(
        self, allowed_category_ids: List[int]
    ) -> Dict[int, List[ReimbursementOrgSettingsAllowedCategoryRule]]:
        """
        Returns a dictionary of all the rules for a given allowed category id
        """

        result = (
            db.session.query(ReimbursementOrgSettingsAllowedCategoryRule)
            .join(
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingsAllowedCategoryRule.reimbursement_organization_settings_allowed_category_id
                == ReimbursementOrgSettingCategoryAssociation.id,
            )
            .filter(
                ReimbursementOrgSettingCategoryAssociation.id.in_(allowed_category_ids)
            )
            .all()
        )

        category_rules_map = defaultdict(list)
        for rule in result:
            category_id = rule.reimbursement_organization_settings_allowed_category_id

            category_rules_map[category_id].append(rule)
        return category_rules_map

    @trace_wrapper
    def get_mapped_allowed_settings(
        self,
    ) -> Dict[int, Dict[int, ReimbursementWalletAllowedCategorySettings]]:
        """
        Returns a nested dictionary with unique allowed category settings results for each category and wallet combination,
        adhering to the unique constraint in the database.
        """
        results = self.session.query(ReimbursementWalletAllowedCategorySettings).all()
        allowed_category_settings_map = defaultdict(lambda: defaultdict())
        for result in results:
            category_id = result.reimbursement_organization_settings_allowed_category_id
            wallet_id = result.reimbursement_wallet_id
            allowed_category_settings_map[category_id][wallet_id] = result
        return allowed_category_settings_map  # type: ignore[return-value] # Incompatible return value type (got "defaultdict[Any, defaultdict[Any, Any]]", expected "Dict[int, Dict[int, ReimbursementWalletAllowedCategorySettings]]")

    @trace_wrapper
    def get_all_allowed_categories_from_org_settings(
        self, reimbursement_org_settings_id: int
    ) -> List[ReimbursementOrgSettingCategoryAssociation]:
        """
        Returns all the allowed category associations for a given ReimbursementOrganizationSettings
        """
        org_settings = self.session.query(ReimbursementOrganizationSettings).get(
            reimbursement_org_settings_id
        )
        if org_settings:
            return org_settings.allowed_reimbursement_categories
        return []

    @trace_wrapper
    def get_all_category_rules_from_allowed_category(
        self, allowed_category_id: int
    ) -> List[ReimbursementOrgSettingsAllowedCategoryRule]:
        """
        Returns a list of all allowed category rules for a given allowed category
        """
        return (
            self.session.query(ReimbursementOrgSettingsAllowedCategoryRule)
            .filter(
                ReimbursementOrgSettingsAllowedCategoryRule.reimbursement_organization_settings_allowed_category_id
                == allowed_category_id
            )
            .all()
        )

    @trace_wrapper
    def get_active_tenure_rule_for_allowed_category(
        self, allowed_category_id: int
    ) -> Optional[ReimbursementOrgSettingsAllowedCategoryRule]:
        today = datetime.datetime.now(datetime.timezone.utc)
        return (
            self.session.query(ReimbursementOrgSettingsAllowedCategoryRule)
            .filter(
                ReimbursementOrgSettingsAllowedCategoryRule.reimbursement_organization_settings_allowed_category_id
                == allowed_category_id,
                ReimbursementOrgSettingsAllowedCategoryRule.rule_name.in_(TENURE_RULES),
                ReimbursementOrgSettingsAllowedCategoryRule.started_at < today,
                ReimbursementOrgSettingsAllowedCategoryRule.started_at is not None,
            )
            .first()
        )

    @trace_wrapper
    def get_all_category_settings_from_allowed_categories_and_wallet(
        self, allowed_category_ids: list, wallet_id: int
    ) -> List[ReimbursementWalletAllowedCategorySettings]:
        """
        Returns a list of reimbursement wallet allowed category settings that are associated with a list of allowed
         categories and a wallet.
        """
        return (
            self.session.query(ReimbursementWalletAllowedCategorySettings)
            .filter(
                ReimbursementWalletAllowedCategorySettings.reimbursement_organization_settings_allowed_category_id.in_(
                    allowed_category_ids
                ),
                ReimbursementWalletAllowedCategorySettings.reimbursement_wallet_id
                == wallet_id,
            )
            .all()
        )

    @trace_wrapper
    def get_all_category_settings_from_wallet(
        self, wallet_id: int
    ) -> List[ReimbursementWalletAllowedCategorySettings]:
        """
        Returns a list of reimbursement wallet allowed category settings that are associated with a wallet
        """
        return (
            self.session.query(ReimbursementWalletAllowedCategorySettings)
            .filter(
                ReimbursementWalletAllowedCategorySettings.reimbursement_wallet_id
                == wallet_id,
            )
            .all()
        )

    @trace_wrapper
    def get_category_setting_from_allowed_category_and_wallet(
        self, allowed_category_id: int, wallet_id: int
    ) -> Optional[ReimbursementWalletAllowedCategorySettings]:
        """
        Returns one reimbursement wallet allowed category settings that is associated with an allowed category and a wallet
        """
        return (
            self.session.query(ReimbursementWalletAllowedCategorySettings)
            .filter(
                ReimbursementWalletAllowedCategorySettings.reimbursement_organization_settings_allowed_category_id
                == allowed_category_id,
                ReimbursementWalletAllowedCategorySettings.reimbursement_wallet_id
                == wallet_id,
            )
            .one_or_none()
        )

    @trace_wrapper
    def get_allowed_categories_by_ids(
        self, allowed_category_ids: list
    ) -> Optional[ReimbursementOrgSettingCategoryAssociation]:
        """
        Returns a list of ReimbursementOrgSettingCategoryAssociation given a list of ids
        """
        return (
            self.session.query(ReimbursementOrgSettingCategoryAssociation)  # type: ignore[return-value] # Incompatible return value type (got "Union[List[TimeLoggedSnowflakeModelBase], Any]", expected "Optional[ReimbursementOrgSettingCategoryAssociation]")
            .filter(
                ReimbursementOrgSettingCategoryAssociation.id.in_(allowed_category_ids)
            )
            .all()
        )

    @trace_wrapper
    def get_all_wallets_by_ids(self, wallet_ids: list) -> List[ReimbursementWallet]:
        """
        Returns a list of ReimbursementWallets given a list of ids
        """
        return (
            self.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id.in_(wallet_ids))
            .all()
        )

    @trace_wrapper
    def get_all_category_settings(
        self,
    ) -> List[ReimbursementWalletAllowedCategorySettings]:
        """
        Returns all reimbursement wallet allowed category settings
        """
        return self.session.query(ReimbursementWalletAllowedCategorySettings).all()

    @trace_wrapper
    def get_category_rule_evaluation_result(
        self, allowed_category_id: int, wallet_id: int
    ) -> ReimbursementWalletCategoryRuleEvaluationResult | None:
        """
        Returns a rule evaluation result for an associated allowed category and wallet
        """
        return (
            self.session.query(ReimbursementWalletCategoryRuleEvaluationResult)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationResult.reimbursement_organization_settings_allowed_category_id
                == allowed_category_id,
                ReimbursementWalletCategoryRuleEvaluationResult.reimbursement_wallet_id
                == wallet_id,
            )
            .one_or_none()
        )

    @trace_wrapper
    def create_rule_evaluation(
        self,
        allowed_category_id: int,
        wallet_id: int,
        result: bool,
        *,
        executed_rules: str | None = None,
        failed_rule: str | None = None,
    ) -> ReimbursementWalletCategoryRuleEvaluationResult:
        """
        Creates and adds a new ReimbursementWalletCategoryRuleEvaluationResult
        """
        evaluated_rule = ReimbursementWalletCategoryRuleEvaluationResult(
            reimbursement_organization_settings_allowed_category_id=allowed_category_id,
            reimbursement_wallet_id=wallet_id,
            executed_category_rule=executed_rules,
            failed_category_rule=failed_rule,
            evaluation_result=result,
        )
        self.session.add(evaluated_rule)
        return evaluated_rule

    @trace_wrapper
    def update_rule_evaluation(
        self,
        evaluated_rule: ReimbursementWalletCategoryRuleEvaluationResult,
        result: bool,
        *,
        executed_rules: str | None = None,
        failed_rule: str | None = None,
    ) -> ReimbursementWalletCategoryRuleEvaluationResult:
        """
        Updates an existing ReimbursementWalletCategoryRuleEvaluationResult
        """
        evaluated_rule.executed_category_rule = executed_rules
        evaluated_rule.failed_category_rule = failed_rule
        evaluated_rule.evaluation_result = result

        self.session.add(evaluated_rule)
        return evaluated_rule

    @trace_wrapper
    def upsert_rule_evaluation(
        self,
        allowed_category_id: int,
        wallet_id: int,
        result: bool,
        *,
        executed_rules: str | None = None,
        failed_rule: str | None = None,
    ) -> None:
        """
        Creates or updates a ReimbursementWalletCategoryRuleEvaluationResult
        """
        insert_statement = Insert(
            ReimbursementWalletCategoryRuleEvaluationResult
        ).values(
            reimbursement_organization_settings_allowed_category_id=allowed_category_id,
            reimbursement_wallet_id=wallet_id,
            executed_category_rule=executed_rules,
            failed_category_rule=failed_rule,
            evaluation_result=result,
        )

        upsert_statement = insert_statement.on_duplicate_key_update(
            executed_category_rule=insert_statement.inserted.executed_category_rule,
            failed_category_rule=insert_statement.inserted.failed_category_rule,
            evaluation_result=insert_statement.inserted.evaluation_result,
        )

        self.session.execute(upsert_statement)
        # Without commit, it's possible that the upserted row is not available for subsequent queries
        self.session.commit()

    @trace_wrapper
    def delete_evaluation_failures(self, result_id: int) -> int:
        """
        Delete the existing failures for a result and return the number of failures deleted
        """
        query = self.session.query(
            ReimbursementWalletCategoryRuleEvaluationFailure
        ).filter(
            ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
            == result_id
        )

        return query.delete()

    @trace_wrapper
    def create_evaluation_failures(
        self, result_id: int, failed_rules: list[str]
    ) -> list[ReimbursementWalletCategoryRuleEvaluationFailure]:
        """
        Add new rule evaluation failures for a result
        """
        failures = [
            ReimbursementWalletCategoryRuleEvaluationFailure(
                evaluation_result_id=result_id, rule_name=rule
            )
            for rule in failed_rules
        ]
        self.session.add_all(failures)
        return failures

    @trace_wrapper
    def get_evaluation_failures(
        self, wallet_id: int, category_id: int
    ) -> list[ReimbursementWalletCategoryRuleEvaluationFailure]:
        """
        Get rule evaluation failures for a wallet and category
        """
        query = (
            self.session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .join(
                ReimbursementWalletCategoryRuleEvaluationResult,
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == ReimbursementWalletCategoryRuleEvaluationResult.id,
            )
            .join(
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingCategoryAssociation.id
                == ReimbursementWalletCategoryRuleEvaluationResult.reimbursement_organization_settings_allowed_category_id,
            )
            .filter(
                ReimbursementWalletCategoryRuleEvaluationResult.reimbursement_wallet_id
                == wallet_id,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == category_id,
            )
        )
        return query.all()

    @trace_wrapper
    def create_allowed_category_setting(
        self,
        allowed_category_id: int,
        wallet_id: int,
        access_level: CategoryRuleAccessLevel,
        access_level_source: CategoryRuleAccessSource,
        updated_by: str | None = None,
    ) -> ReimbursementWalletAllowedCategorySettings:
        """
        Creates and adds a new ReimbursementWalletAllowedCategorySettings
        """
        if updated_by is None:
            updated_by = SYSTEM_USER

        category_setting = ReimbursementWalletAllowedCategorySettings(
            reimbursement_organization_settings_allowed_category_id=allowed_category_id,
            reimbursement_wallet_id=wallet_id,
            updated_by=updated_by,
            access_level=access_level,
            access_level_source=access_level_source,
        )
        try:
            self.session.add(category_setting)
            self.session.flush()
        # The OperationalError handles the deadlock that occurs when 2 duelling processes attempt to insert the same new
        # row at the same time. This is distinct from the Integrity error, but the handling is the same.
        except (IntegrityError, OperationalError) as e:
            log.warn(
                "Integrity/Operational Error. Attempting to create a category setting that already exists.",
                allowed_category_id=allowed_category_id,
                wallet_id=str(wallet_id),
                error=str(e),
                traceback=format_exc(),
            )
            self.session.rollback()
            found_category_settings = (
                self.get_category_setting_from_allowed_category_and_wallet(
                    allowed_category_id=allowed_category_id, wallet_id=wallet_id
                )
            )
            if (
                found_category_settings
                and found_category_settings.access_level != access_level
            ):
                log.info(
                    "Found existing category setting. Updating.",
                    allowed_category_id=allowed_category_id,
                    wallet_id=str(wallet_id),
                    old_access_level=str(found_category_settings.access_level),
                    new_access_level=str(access_level),
                )
                category_setting = self.update_allowed_category_setting(
                    category_setting=found_category_settings,
                    access_level=access_level,
                    access_level_source=access_level_source,
                )
        return category_setting

    @trace_wrapper
    def upsert_allowed_category_setting(
        self,
        allowed_category_id: int,
        wallet_id: int,
        access_level: CategoryRuleAccessLevel,
        access_level_source: CategoryRuleAccessSource,
        updated_by: str | None = None,
    ) -> None:
        """
        Creates and adds a new ReimbursementWalletAllowedCategorySettings
        """
        if updated_by is None:
            updated_by = SYSTEM_USER

        insert_statement = Insert(ReimbursementWalletAllowedCategorySettings).values(
            reimbursement_organization_settings_allowed_category_id=allowed_category_id,
            reimbursement_wallet_id=wallet_id,
            access_level=access_level,
            access_level_source=access_level_source,
            updated_by=updated_by,
        )

        upsert_statement = insert_statement.on_duplicate_key_update(
            access_level=insert_statement.inserted.access_level,
            access_level_source=insert_statement.inserted.access_level_source,
            updated_by=insert_statement.inserted.updated_by,
        )

        self.session.execute(upsert_statement)
        # Without commit, it's possible that the upserted row is not available for subsequent queries
        self.session.commit()

    @trace_wrapper
    def update_allowed_category_setting(
        self,
        category_setting: ReimbursementWalletAllowedCategorySettings,
        access_level: CategoryRuleAccessLevel,
        access_level_source: CategoryRuleAccessSource,
        updated_by: str | None = None,
    ) -> ReimbursementWalletAllowedCategorySettings:
        """
        Updates an existing ReimbursementWalletAllowedCategorySettings
        """
        if updated_by is None:
            updated_by = SYSTEM_USER

        category_setting.updated_by = updated_by
        category_setting.access_level = access_level  # type: ignore[assignment] # Incompatible types in assignment (expression has type "CategoryRuleAccessLevel", variable has type "str")
        category_setting.access_level_source = access_level_source  # type: ignore[assignment] # Incompatible types in assignment (expression has type "CategoryRuleAccessSource", variable has type "str")

        self.session.add(category_setting)
        return category_setting

    @trace_wrapper
    def get_wallet_allowed_categories_and_access_level(
        self, wallet_id: int, org_settings_id: int
    ) -> list[AllowedCategoryAccessLevel]:
        """
        Returns ReimbursementOrgSettingCategoryAssociation.id + access level from the associated
        ReimbursementWalletAllowedCategorySettings records
        """
        query = """
            SELECT
                reimbursement_organization_settings_allowed_category.id AS allowed_category_id,
                reimbursement_wallet_allowed_category_settings.access_level AS wallet_access_level
            FROM
                reimbursement_organization_settings_allowed_category
            LEFT JOIN
                reimbursement_wallet_allowed_category_settings
            ON
                reimbursement_organization_settings_allowed_category.id = reimbursement_wallet_allowed_category_settings.reimbursement_organization_settings_allowed_category_id
            AND
                reimbursement_wallet_allowed_category_settings.reimbursement_wallet_id = :wallet_id
            WHERE
                reimbursement_organization_settings_allowed_category.reimbursement_organization_settings_id = :org_settings_id
        """
        result = self.session.execute(
            query,
            {
                "wallet_id": wallet_id,
                "org_settings_id": org_settings_id,
            },
        ).fetchall()
        return [
            AllowedCategoryAccessLevel(
                allowed_category_id=r["allowed_category_id"],
                wallet_access_level=r["wallet_access_level"],
            )
            for r in result
        ]

from __future__ import annotations

import datetime
import traceback
from traceback import format_exc
from typing import Generator, List, Optional

import sqlalchemy
from maven import observability
from maven.feature_flags import bool_variation
from rq import get_current_job
from sqlalchemy.exc import IntegrityError

from cost_breakdown.constants import IS_INTEGRATIONS_K8S_CLUSTER
from storage.connection import db
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper
from wallet.models.constants import (
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    WalletState,
)
from wallet.models.models import (
    AllowedCategoryAccessLevel,
    CategoryRuleProcessingResultSchema,
)
from wallet.models.reimbursement import ReimbursementPlan
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingsAllowedCategoryRule,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWallet,
    ReimbursementWalletAllowedCategorySettings,
    ReimbursementWalletCategoryRuleEvaluationFailure,
    ReimbursementWalletCategoryRuleEvaluationResult,
)
from wallet.repository.reimbursement_category_activation import (
    CategoryActivationRepository,
)
from wallet.services.reimbursement_category_activation_constants import (
    RULE_REGISTRATION_MAP,
)
from wallet.services.reimbursement_category_activation_rules import (
    AbstractCategoryRule,
    ActionableCategoryActivationException,
    TenureCategoryRule,
)
from wallet.tasks.alegeus import enroll_member_account
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    configure_wallet_allowed_category,
)
from wallet.utils.eligible_wallets import get_user_eligibility_start_date

log = logger(__name__)


class CategoryActivationService:
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        self.session = session or db.session
        self.rules_repo: CategoryActivationRepository = CategoryActivationRepository(
            session=self.session
        )

    @staticmethod
    @observability.wrap
    def get_category_rule(rule_name: str) -> AbstractCategoryRule:
        """
        Returns the AbstractCategoryRule class given a rule name if exists
        """
        rule_class = RULE_REGISTRATION_MAP.get(rule_name)
        if rule_class is None:
            log.error("Rule not found", rule_name=rule_name)
            raise ActionableCategoryActivationException(
                "Rule not found in RULE_REGISTRATION_MAP."
            )
        return rule_class()

    @staticmethod
    @observability.wrap
    def execute_category_rule(
        wallet: ReimbursementWallet,
        rule: AbstractCategoryRule,
        association: ReimbursementOrgSettingCategoryAssociation,
    ) -> bool:
        """
        Returns the evaluated rule result from the AbstractCategoryRule class invoked.
        """
        try:
            evaluated_rule_result = rule.execute(wallet=wallet, association=association)
        except NotImplementedError as e:
            log.error("Rule not implemented.", wallet_id=str(wallet.id))
            raise ActionableCategoryActivationException(
                message="Rule not implemented!"
            ) from e
        return evaluated_rule_result

    @observability.wrap
    def get_start_date_for_user_allowed_category(
        self,
        plan: ReimbursementPlan,
        user_id: int,
        allowed_category: Optional[ReimbursementOrgSettingCategoryAssociation],
    ) -> Optional[datetime.date]:
        """
        Access to a category is determined by wallet eligibility and per-category tenure rules,
        with org-level plans as a fallback starting date. Note that we use employee_start_date and not the
        WalletEnablement start date as employee_start_date is a much more reliable value.
        HDHP plans do not have per-category tenure rules; they only use plan/eligibility date.
        # See https://mavenclinic.atlassian.net/browse/PAY-6234
        """
        start_date = plan.start_date  # fallback
        e9y_start_date = get_user_eligibility_start_date(
            user_id=user_id, org_id=plan.organization_id
        )
        if e9y_start_date:
            start_date = e9y_start_date
        if allowed_category:
            category_rule = self.rules_repo.get_active_tenure_rule_for_allowed_category(
                allowed_category_id=allowed_category.id
            )
            if category_rule:
                rule = CategoryActivationService.get_category_rule(
                    rule_name=category_rule.rule_name
                )
                if isinstance(rule, TenureCategoryRule) and start_date is not None:
                    start_date = rule.add_tenure_to_start_date(start_date)
        if start_date and start_date < plan.start_date:
            # If a user is eligible for a plan before that plan starts, the effective start date is the plan start
            start_date = plan.start_date
        return start_date

    @observability.wrap
    def process_allowed_categories_that_have_rules(
        self, bypass_alegeus: bool, commit_size: int
    ) -> Generator[list[CategoryRuleProcessingResultSchema]]:  # type: ignore[type-arg] # "Generator" expects 3 type arguments, but 1 given
        """
        Evaluates and runs rules for all wallets that belong to an allowed categories with associated rules.
        Creates/updates and stores each wallet rule evaluation results and allowed category settings records.
        """
        yield_counter = 0
        results = []
        allowed_category_ids = (
            self.rules_repo.get_all_allowed_category_ids_that_have_rules()
        )
        if not allowed_category_ids:
            log.info("No allowed_category_ids found.")
            return results

        mapped_category_wallets = (
            self.rules_repo.get_all_wallets_from_allowed_categories(
                allowed_category_ids=allowed_category_ids
            )
        )
        mapped_category_rules = (
            self.rules_repo.get_all_category_rules_for_allowed_categories(
                allowed_category_ids=allowed_category_ids
            )
        )

        mapped_allowed_settings = self.rules_repo.get_mapped_allowed_settings()

        for category_id in allowed_category_ids:
            wallets = mapped_category_wallets.get(category_id, [])
            all_category_rules = mapped_category_rules.get(category_id, [])
            for wallet in wallets:
                yield_counter += 1
                log.info("Processing item", yield_counter=yield_counter)
                result = CategoryRuleProcessingResultSchema()
                result.wallet_id = wallet.id
                result.category_id = category_id
                results.append(result)
                try:
                    result.rule_evaluation_result = self.evaluate_and_process_rules(
                        category_id=category_id,
                        wallet=wallet,
                        all_category_rules=all_category_rules,
                    )
                    setting = self.save_category_settings(
                        category_id=category_id,
                        wallet=wallet,
                        evaluation_result=result.rule_evaluation_result,  # type: ignore[arg-type] # Argument "evaluation_result" to "save_category_settings" of "CategoryActivationService" has incompatible type "Optional[bool]"; expected "bool"
                        has_rules=True,
                        mapped_settings_results=mapped_allowed_settings,
                        bypass_alegeus=bypass_alegeus,
                    )
                    result.setting_id = setting.id
                    result.success = True
                except IntegrityError as e:
                    log.error(
                        "Integrity exception raised processing wallet without rules.",
                        category_id=str(category_id),
                        wallet_id=str(wallet.id),
                        error=str(e),
                        traceback=format_exc(),
                    )
                    self.session.rollback()
                    result.success = False
                except ActionableCategoryActivationException as e:
                    log.error(
                        "Actionable exception raised processing wallet with rules.",
                        category_id=str(category_id),
                        wallet_id=str(wallet.id),
                        error=str(e),
                        traceback=format_exc(),
                    )
                    self.session.rollback()
                    result.success = False
                except Exception as e:
                    log.error(
                        "Exception raised processing wallet with rules.",
                        category_id=str(category_id),
                        wallet_id=str(wallet.id),
                        error=str(e),
                        traceback=format_exc(),
                    )
                    result.success = False
                if not yield_counter % commit_size:
                    log.info("Intermediate yield.", yield_counter=yield_counter)
                    yield results
                    results = []
        log.info("Final yield.", yield_counter=yield_counter)
        yield results

    @observability.wrap
    def process_allowed_categories_without_rules(
        self, bypass_alegeus: bool, commit_size: int
    ) -> Generator[list[CategoryRuleProcessingResultSchema]]:  # type: ignore[type-arg] # "Generator" expects 3 type arguments, but 1 given
        """
        Processes all wallets that belong to an allowed categories without associated rules.
        Stores category settings records with full access visibility for each allowed category.
        Implemented as a generator that periodically yields to allow the called to commit the changes.
        :param bypass_alegeus: True to bypass alegeus
        :param commit_size: The number of iterations until the generator yields. If 0, will commit as one chunk.
        Not recommended
        :return:
        :rtype:
        """
        if commit_size < 0:
            raise ValueError(f"{commit_size=} is less than 0.")
        yield_counter = 0
        results = []
        allowed_category_ids = (
            self.rules_repo.get_all_allowed_category_ids_without_rules()
        )
        if not allowed_category_ids:
            log.info("No allowed_category_ids found.")
            return results

        mapped_category_wallets = (
            self.rules_repo.get_all_wallets_from_allowed_categories(
                allowed_category_ids=allowed_category_ids
            )
        )
        mapped_allowed_settings = self.rules_repo.get_mapped_allowed_settings()

        for category_id in allowed_category_ids:
            wallets = mapped_category_wallets.get(category_id, [])
            for wallet in wallets:
                yield_counter += 1
                log.info("Processing item", yield_counter=yield_counter)
                result = CategoryRuleProcessingResultSchema()
                result.wallet_id = wallet.id
                result.category_id = category_id
                result.rule_evaluation_result = True
                results.append(result)
                try:
                    setting = self.save_category_settings(
                        category_id=category_id,
                        wallet=wallet,
                        has_rules=False,
                        mapped_settings_results=mapped_allowed_settings,
                        bypass_alegeus=bypass_alegeus,
                    )
                    result.setting_id = setting.id
                    result.success = True
                except IntegrityError as e:
                    log.error(
                        "Integrity exception raised processing wallet without rules.",
                        category_id=str(category_id),
                        wallet_id=str(wallet.id),
                        error=str(e),
                        traceback=format_exc(),
                    )
                    self.session.rollback()
                    result.success = False
                except ActionableCategoryActivationException as e:
                    log.error(
                        "Actionable exception raised processing wallet without rules.",
                        category_id=str(category_id),
                        wallet_id=str(wallet.id),
                        error=str(e),
                        traceback=format_exc(),
                    )
                    result.success = False
                except Exception as e:
                    log.error(
                        "Exception raised processing wallet with rules.",
                        category_id=str(category_id),
                        wallet_id=str(wallet.id),
                        error=str(e),
                        traceback=format_exc(),
                    )
                if not yield_counter % commit_size:
                    log.info("Intermediate yield.", yield_counter=yield_counter)
                    if commit_size:
                        yield results
                        results = []
        log.info("Final yield.", yield_counter=yield_counter)
        yield results

    @observability.wrap
    def get_wallet_allowed_categories(
        self, wallet: ReimbursementWallet, bypass_alegeus: bool = False
    ) -> List[ReimbursementOrgSettingCategoryAssociation]:
        """
        Retrieves all the allowed category records that have associated settings and filters them by access level. If no
        setting is found, the rule evaluator is processed and stored to determine visibility.
        """
        org_settings_id = wallet.reimbursement_organization_settings_id
        results: list[
            AllowedCategoryAccessLevel
        ] = self.rules_repo.get_wallet_allowed_categories_and_access_level(
            wallet_id=wallet.id, org_settings_id=org_settings_id
        )
        allowed_category_ids = []
        for row in results:
            allowed_category_id = row["allowed_category_id"]
            wallet_access_level = row["wallet_access_level"]
            if wallet_access_level is not None:
                log.info(
                    "Wallet access level for allowed category",
                    wallet_id=str(wallet.id),
                    category_id=str(allowed_category_id),
                    access_level=wallet_access_level,
                )
                if wallet_access_level == CategoryRuleAccessLevel.FULL_ACCESS.value:
                    allowed_category_ids.append(allowed_category_id)
            else:
                log.info(
                    "Category settings not found. Processing wallet category rule.",
                    allowed_category_id=str(allowed_category_id),
                    wallet_id=str(wallet.id),
                )
                try:
                    bypass_alegeus = (
                        bypass_alegeus or wallet.state != WalletState.QUALIFIED
                    )
                    setting = self.process_wallet_category_rule(
                        allowed_category_id=allowed_category_id,
                        wallet=wallet,
                        process_delay=True,
                        bypass_alegeus=bypass_alegeus,
                    )
                    if (
                        setting
                        and setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS
                    ):
                        allowed_category_ids.append(allowed_category_id)
                except Exception as e:
                    log.error(
                        "Exception get_wallet_allowed_categories.",
                        wallet_id=str(wallet.id),
                        allowed_category_id=str(allowed_category_id),
                        error=str(e),
                        traceback=format_exc(),
                    )

        wallet_allowed_categories = self.rules_repo.get_allowed_categories_by_ids(
            allowed_category_ids=allowed_category_ids
        )
        if not wallet_allowed_categories:
            log.error("Wallet has no allowed categories.", wallet_id=str(wallet.id))

        return wallet_allowed_categories

    @observability.wrap
    def process_wallet_category_rule(
        self,
        allowed_category_id: int,
        wallet: ReimbursementWallet,
        process_delay: bool = False,
        bypass_alegeus: bool = False,
    ) -> ReimbursementWalletAllowedCategorySettings:
        """
        Runs the rule evaluation for a wallet and allowed category and updates the db with results and
        a category settings object. If no rule, create an allowed category setting.
        """
        mapped_settings_result = {
            allowed_category_id: {
                wallet.id: self.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                    allowed_category_id=allowed_category_id, wallet_id=wallet.id
                )
            }
        }
        # Get all of the rules for this category
        all_category_rules = (
            self.rules_repo.get_all_category_rules_from_allowed_category(
                allowed_category_id=allowed_category_id
            )
        )
        if all_category_rules:
            evaluation_result = self.evaluate_and_process_rules(
                category_id=allowed_category_id,
                wallet=wallet,
                all_category_rules=all_category_rules,
            )
            setting = self.save_category_settings(
                category_id=allowed_category_id,
                wallet=wallet,
                has_rules=True,
                mapped_settings_results=mapped_settings_result,
                evaluation_result=evaluation_result,
                process_delay=process_delay,
                bypass_alegeus=bypass_alegeus,
            )
        else:
            setting = self.save_category_settings(
                category_id=allowed_category_id,
                wallet=wallet,
                has_rules=False,
                process_delay=process_delay,
                bypass_alegeus=bypass_alegeus,
                mapped_settings_results=mapped_settings_result,
            )
        return setting

    @observability.wrap
    def evaluate_and_process_rules(
        self,
        category_id: int,
        wallet: ReimbursementWallet,
        all_category_rules: List[ReimbursementOrgSettingsAllowedCategoryRule],
    ) -> bool:
        """
        Evaluates all category rules for a category and a wallet and stores and returns the evaluated result.
        """
        persist_rule_failures = bool_variation(
            "release-persist-rule-failures",
            default=False,
        )
        log.info(
            "Beginning rule evaluation.",
            inp_category_id=str(category_id),
            inp_wallet_id=str(wallet.id),
            persist_rule_failures=str(persist_rule_failures),
        )

        failed_rules_string, success_rules_string = None, None
        failed_rules, evaluated_rules = [], []

        if persist_rule_failures:
            (
                evaluation_result,
                evaluated_rules,
                failed_rules,
            ) = self.evaluate_all_rules_for_wallet(
                wallet=wallet, all_category_rules=all_category_rules
            )
        else:
            evaluation_result, rules_string = self.evaluate_rules_for_wallet(
                wallet=wallet, all_category_rules=all_category_rules
            )
            failed_rules_string, success_rules_string = self.get_rules_strings(
                rules_string=rules_string, evaluation_result=evaluation_result
            )

        saved_rule_evaluation_record: ReimbursementWalletCategoryRuleEvaluationResult = self.save_rule_evaluation_record(
            category_id=category_id,
            wallet_id=wallet.id,
            rule_result=evaluation_result,
            failed_rules_string=failed_rules_string,
            success_rules_string=success_rules_string,
        )

        if persist_rule_failures:
            # Save the failed rules
            self.save_rule_evaluation_failures(
                saved_rule_evaluation_record=saved_rule_evaluation_record,
                failed_rules=failed_rules,
            )

        log.info(
            "Completed rule evaluation.",
            inp_category_id=str(category_id),
            inp_wallet_id=str(wallet.id),
            op_evaluation_result=evaluation_result,
            persist_rule_failures=str(persist_rule_failures),
        )
        return evaluation_result

    @observability.wrap
    def evaluate_rules_for_wallet(
        self,
        wallet: ReimbursementWallet,
        all_category_rules: List[ReimbursementOrgSettingsAllowedCategoryRule],
    ) -> tuple[bool, str]:
        """
        Returns a tuple of the result of the rule evaluation as a bool and the rules that were evaluated as a string
        """
        evaluated_rules_string = ""
        evaluated_rule, started_at_enabled = None, None
        for category_rule in all_category_rules:
            try:
                started_at_enabled = bool(
                    category_rule.started_at
                    and category_rule.started_at <= datetime.datetime.utcnow()
                )
                rule_class = self.get_category_rule(rule_name=category_rule.rule_name)
                evaluated_rule = self.execute_category_rule(
                    wallet=wallet,
                    rule=rule_class,
                    association=category_rule.reimbursement_organization_settings_allowed_category,
                )
            except ActionableCategoryActivationException as e:
                log.error(
                    "Exception within evaluate_rules_for_wallet.",
                    error=str(e),
                    wallet_id=str(wallet.id),
                    category_rule_id=str(category_rule.id),
                    started_at_enabled=started_at_enabled,
                )
            if not evaluated_rule or not started_at_enabled:
                evaluated_rules_string += f"{category_rule.rule_name}"
                return False, evaluated_rules_string
            else:
                evaluated_rules_string += f"{category_rule.rule_name} "
        return True, evaluated_rules_string

    @observability.wrap
    def evaluate_all_rules_for_wallet(
        self,
        wallet: ReimbursementWallet,
        all_category_rules: List[ReimbursementOrgSettingsAllowedCategoryRule],
    ) -> tuple[bool, list[str], list[str]]:
        """
        Evaluates category rules associated with a wallet and returns the overall result,
        a list of all evaluated rule names, and a list of failed rule names.

        Args:
            wallet: The ReimbursementWallet object.
            all_category_rules: A list of ReimbursementOrgSettingsAllowedCategoryRule objects.

        Returns:
            A tuple containing:
            - A boolean indicating the overall evaluation result (True if all rules passed, False otherwise).
            - A list of strings containing the names of all evaluated rules.
            - A list of strings containing the names of the rules that failed evaluation.
        """

        evaluated_rules: list[str] = []
        failed_rules: list[str] = []

        for category_rule in all_category_rules:
            rule_name: str = category_rule.rule_name
            evaluated_rules.append(rule_name)

            # Check if the rule is enabled - if not, that counts as a failure
            if (
                started_at_enabled := bool(
                    category_rule.started_at
                    and category_rule.started_at <= datetime.datetime.utcnow()
                )
            ) is False:
                failed_rules.append(rule_name)
                continue

            try:
                rule_class = self.get_category_rule(rule_name=rule_name)
                rule_passed: bool = self.execute_category_rule(
                    wallet=wallet,
                    rule=rule_class,
                    association=category_rule.reimbursement_organization_settings_allowed_category,
                )
                if not rule_passed:
                    failed_rules.append(rule_name)

            except ActionableCategoryActivationException as e:
                log.error(
                    "Exception within evaluate_all_rules_for_wallet.",
                    error=str(e),
                    wallet_id=str(wallet.id),
                    category_rule_id=str(category_rule.id),
                    started_at_enabled=started_at_enabled,
                )
                failed_rules.append(rule_name)  # Consider exception as rule failure

        return not bool(failed_rules), evaluated_rules, failed_rules

    @observability.wrap
    def save_rule_evaluation_record(
        self,
        category_id: int,
        wallet_id: int,
        rule_result: bool,
        failed_rules_string: str | None = None,
        success_rules_string: str | None = None,
    ) -> ReimbursementWalletCategoryRuleEvaluationResult:
        """
        Creates or updates a rule evaluation result.
        """
        try:
            self.rules_repo.upsert_rule_evaluation(
                allowed_category_id=category_id,
                wallet_id=wallet_id,
                result=rule_result,
                executed_rules=success_rules_string,
                failed_rule=failed_rules_string,
            )

            updated_rule_evaluation_record = (
                self.rules_repo.get_category_rule_evaluation_result(
                    allowed_category_id=category_id,
                    wallet_id=wallet_id,
                )
            )

            self.rules_repo.session.refresh(updated_rule_evaluation_record)
        except Exception as e:
            log.exception(
                "Unhandled exception save_rule_evaluation_record.",
                error=str(e),
                traceback=format_exc(),
                wallet_id=str(wallet_id),
                category_id=(str(category_id)),
                evaluation_result=rule_result,
            )
            raise e

        return updated_rule_evaluation_record

    @observability.wrap
    def save_rule_evaluation_failures(
        self,
        saved_rule_evaluation_record: ReimbursementWalletCategoryRuleEvaluationResult,
        failed_rules: list[str],
    ) -> list[ReimbursementWalletCategoryRuleEvaluationFailure]:
        failures = []
        # Delete all previous failures
        self.rules_repo.delete_evaluation_failures(
            result_id=saved_rule_evaluation_record.id
        )

        # if evaluation_result is True -> Save the new failures
        if saved_rule_evaluation_record.evaluation_result is False and failed_rules:
            failures = self.rules_repo.create_evaluation_failures(
                result_id=saved_rule_evaluation_record.id, failed_rules=failed_rules
            )

        return failures

    @observability.wrap
    def save_category_settings(
        self,
        category_id: int,
        wallet: ReimbursementWallet,
        has_rules: bool,
        mapped_settings_results: dict,
        evaluation_result: bool | None = None,
        process_delay: bool = False,
        bypass_alegeus: bool = False,
    ) -> ReimbursementWalletAllowedCategorySettings:
        """
        Creates or updates an allowed category setting.
        """
        log.info(
            "Beginning category setting (in memory) save.",
            inp_category_id=str(category_id),
            inp_wallet_id=str(wallet.id),
            inp_evaluation_result=evaluation_result,
            process_delay=process_delay,
            bypass_alegeus=bypass_alegeus,
        )
        access_level, access_source = self.get_access_level_and_source(
            has_rules=has_rules, evaluation_result=evaluation_result
        )
        setting = mapped_settings_results.get(category_id, {}).get(wallet.id, None)
        historical_access_level = None
        try:
            if setting:
                log.info(
                    "Wallet access level source for category",
                    wallet_id=str(wallet.id),
                    category_id=str(category_id),
                    access_level_source=setting.access_level_source,
                )
                historical_access_level = setting.access_level
                if setting.access_level_source != CategoryRuleAccessSource.OVERRIDE:
                    setting = self.rules_repo.update_allowed_category_setting(
                        category_setting=setting,
                        access_level=access_level,
                        access_level_source=access_source,
                    )
            else:
                self.rules_repo.upsert_allowed_category_setting(
                    allowed_category_id=category_id,
                    wallet_id=wallet.id,
                    access_level=access_level,
                    access_level_source=access_source,
                )
                setting = self.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                    allowed_category_id=category_id, wallet_id=wallet.id
                )
                # Reload from DB since sqlalchemy's in-memory representation doesn't have the latest upserted values
                self.rules_repo.session.refresh(setting)

            # Only configure accounts in Alegeus that are given Full Access for the first time via Rules
            if (
                setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS
                and historical_access_level != CategoryRuleAccessLevel.FULL_ACCESS
                and not bypass_alegeus
            ):
                if process_delay:
                    current_job = get_current_job()
                    if current_job or IS_INTEGRATIONS_K8S_CLUSTER:
                        stack_trace = traceback.format_stack()
                        full_stack_trace = "\n".join(stack_trace)
                        log.info(
                            "Already running within an RQ context or an unsupported env; suppressing nested RQ spinoff.",
                            current_job=current_job,
                            full_stack_trace=full_stack_trace,
                            wallet_id=wallet.id,
                            allowed_category_id=category_id,
                            process_delay=process_delay,
                            in_integrations_cluster=IS_INTEGRATIONS_K8S_CLUSTER,
                        )
                        configure_wallet_allowed_category(
                            wallet=wallet, allowed_category_id=category_id
                        )
                    else:
                        log.info(
                            "Not running within an RQ context; spinning off RQ job.",
                            wallet_id=wallet.id,
                            allowed_category_id=category_id,
                            process_delay=process_delay,
                        )
                        service_ns_tag = "wallet"
                        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                        enroll_member_account.delay(
                            wallet_id=wallet.id,
                            allowed_category_id=category_id,
                            service_ns=service_ns_tag,
                            team_ns=team_ns_tag,
                        )
                else:
                    log.info(
                        "Running within the same context (process delay not requested)",
                        wallet_id=wallet.id,
                        allowed_category_id=category_id,
                        process_delay=process_delay,
                    )
                    configure_wallet_allowed_category(
                        wallet=wallet, allowed_category_id=category_id
                    )
        except Exception as e:
            log.error(
                "Exception save_rule_evaluation_record.",
                error=str(e),
                traceback=format_exc(),
                wallet_id=str(wallet.id),
                category_id=(str(category_id)),
            )
            raise ActionableCategoryActivationException(
                message="Exception save_rule_evaluation_record."
            ) from e
        log.info(
            "Saved setting in memory.",
            inp_category_id=str(category_id),
            inp_wallet_id=str(wallet.id),
            inp_evaluation_result_id=evaluation_result,
            op_setting_id=str(setting.id),
        )
        return setting

    @staticmethod
    @observability.wrap
    def get_rules_strings(rules_string: str, evaluation_result: bool) -> (str, str):  # type: ignore[syntax] # Syntax error in type annotation
        """
        Accepts a rule evaluation and returns the appropriate rule string value for failed and successful values.
        """
        failed_rules_string, success_rules_string = None, None
        success_rules_string = (
            rules_string if evaluation_result else success_rules_string
        )
        failed_rules_string = (
            rules_string if not evaluation_result else failed_rules_string
        )
        return failed_rules_string, success_rules_string

    @staticmethod
    @observability.wrap
    def get_access_level_and_source(
        has_rules: bool, evaluation_result: bool | None = None
    ) -> (CategoryRuleAccessLevel, CategoryRuleAccessSource):  # type: ignore[syntax] # Syntax error in type annotation
        """
        Sets the rule access level and source based on inputs.
        """
        access_level = CategoryRuleAccessLevel.FULL_ACCESS
        if has_rules:
            access_level = (
                CategoryRuleAccessLevel.FULL_ACCESS
                if evaluation_result
                else CategoryRuleAccessLevel.NO_ACCESS
            )
            access_source = CategoryRuleAccessSource.RULES
        else:
            access_source = CategoryRuleAccessSource.NO_RULES
        return access_level, access_source

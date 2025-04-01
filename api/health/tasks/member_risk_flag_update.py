import traceback
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import ddtrace
from maven import feature_flags
from sqlalchemy.orm import joinedload

from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.health_profile import HealthProfile
from health.services.member_risk_calc_service import MemberRiskCalcService
from health.services.member_risk_service import MemberRiskService
from health.services.risk_service import RiskService
from models.tracks.member_track import MemberTrack
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

split_cron_in_half_enabled = feature_flags.bool_variation(
    "split-nightly-risk-calculation-cron-into-half",
    default=False,
)

# Runs all RiskCalculators against All Users as part of nightly cronjob
# Fetches data in batches of users to reduce #queries
class MemberRiskFlagUpdateTask:
    def __init__(self) -> None:
        self.risk_service = RiskService()
        self.batch_size = 10000

        # The cronjob also has a timeout. This is lower so that it ends & logs info gracefully
        self.max_runtime = timedelta(hours=1)

        # stats
        self.num_users_processed: int = 0
        self.num_users_updated: int = 0
        self.num_created_by_risk_name: Dict[str, int] = {}
        self.num_ended_by_risk_name: Dict[str, int] = {}
        self.num_updated_by_risk_name: Dict[str, int] = {}
        self.error_count: int = 0

    def _get_user_ids(self) -> Iterator[int]:
        # Get Users with an Active Track
        #   since Risks are only meaningful to providers/coaches,
        #   and a Member needs a Track to have a Coach)
        # Todo Filter active users further (User.active doesn't seem very useful)
        last_id = -1
        done = False
        while not done:
            results = (
                db.session.query(MemberTrack.user_id)
                .filter(MemberTrack.active == True, MemberTrack.user_id > last_id)
                .order_by(MemberTrack.user_id)
                .distinct()
                .limit(self.batch_size)
                .all()
            )
            for item in results:
                last_id = item[0]
                yield item[0]
            if len(results) < self.batch_size:
                done = True

    def _batch(self, user_ids: Iterable[int]) -> Iterable[List[int]]:
        batch = []
        for user_id in user_ids:
            batch.append(user_id)
            if (len(batch)) == self.batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def run(self, user_ids: Optional[Iterable[int]] = None) -> None:
        start = datetime.utcnow()
        log.info("MemberRiskFlagUpdateTask - Starting")
        if not user_ids:
            user_ids = self._get_user_ids()

        message = "MemberRiskFlagUpdateTask - Completed"
        try:
            batch_num = 0
            for batch in self._batch(user_ids):
                batch_num += 1
                self._log_stats(f"Running User Batch {batch_num}")
                self._run_for_user_batch(batch)
                if self.error_count > 20:
                    message = "MemberRiskFlagUpdateTask - Aborted Due to Error Count"
                    break
                run_time = datetime.utcnow() - start
                if run_time > self.max_runtime:
                    message = "MemberRiskFlagUpdateTask - Aborted, Exceeded max runtime"
                    break
        except Exception as e:
            message = "MemberRiskFlagUpdateTask - Aborted Due to Exception"
            raise e
        finally:
            self._log_stats(message)

    def _run_for_user_batch(self, user_ids: List[int]) -> None:
        health_profile_by_user = self._get_health_profiles(user_ids)
        active_risks_by_user = self._get_active_member_risks(user_ids)
        active_tracks_by_user = self._get_active_member_tracks(user_ids)
        for user_id in user_ids:
            hp = health_profile_by_user.get(user_id, None)
            active_risks = active_risks_by_user.get(user_id, [])
            active_tracks = active_tracks_by_user.get(user_id, [])
            if hp:
                self._run_for_user(user_id, hp, active_risks, active_tracks)
        db.session.commit()

    def _run_for_user(
        self,
        user_id: int,
        health_profile: HealthProfile,
        active_risks: List[MemberRiskFlag],
        active_tracks: List[str],
    ) -> None:
        self.num_users_processed += 1
        member_risk_service = MemberRiskService(
            user_id,
            health_profile=health_profile,
            modified_reason="MemberRiskFlagUpdateTask",
            risk_service=self.risk_service,  # so that Risk Flag Lookup by name gets cached
            confirm_existing_risks=False,  # don't want existing risks to be modified reach run
            commit=False,
        )
        member_risk_service._set_active_risk_cache(active_risks)

        calc_service = MemberRiskCalcService(member_risk_service, active_tracks)
        result = calc_service.run_all()

        for name in result.risks_added:
            self.num_created_by_risk_name[name] = (
                self.num_created_by_risk_name.get(name, 0) + 1
            )
        for name in result.risks_ended:
            self.num_ended_by_risk_name[name] = (
                self.num_ended_by_risk_name.get(name, 0) + 1
            )
        for name in result.risks_updated:
            self.num_updated_by_risk_name[name] = (
                self.num_updated_by_risk_name.get(name, 0) + 1
            )
        if result.risks_added or result.risks_ended or result.risks_updated:
            self.num_users_updated += 1
        self.error_count += result.error_count

    def _get_health_profiles(self, user_ids: List[int]) -> Dict[int, HealthProfile]:
        health_profiles: List[HealthProfile] = (
            db.session.query(HealthProfile)
            .filter(HealthProfile.user_id.in_(user_ids))
            .all()
        )
        health_profile_by_user = {}
        for hp in health_profiles:
            health_profile_by_user[hp.user_id] = hp
        return health_profile_by_user

    def _get_active_member_risks(
        self, user_ids: List[int]
    ) -> Dict[int, List[MemberRiskFlag]]:
        member_risks: List[MemberRiskFlag] = (
            db.session.query(MemberRiskFlag)
            .filter(MemberRiskFlag.user_id.in_(user_ids))
            .filter(MemberRiskFlag.end.is_(None))
            .all()
        )
        member_risks_by_user = defaultdict(list)
        for mr in member_risks:
            member_risks_by_user[mr.user_id].append(mr)
        return member_risks_by_user

    def _get_active_member_tracks(self, user_ids: List[int]) -> Dict[int, List[str]]:
        member_tracks: List[MemberTrack] = (
            db.session.query(MemberTrack)
            .filter(MemberTrack.user_id.in_(user_ids))
            .filter(MemberTrack.active == True)
            .all()
        )
        member_tracks_by_user = defaultdict(list)
        for mt in member_tracks:
            member_tracks_by_user[mt.user_id].append(mt.name)
        return member_tracks_by_user  # type: ignore

    def _log_stats(self, message: str) -> None:
        log.info(
            message,
            context={
                "num_users_processed": self.num_users_processed,
                "num_users_updated": self.num_users_updated,
                "risks_created": self.num_created_by_risk_name,
                "risks_ended": self.num_ended_by_risk_name,
                "risks_updated": self.num_updated_by_risk_name,
            },
        )


class NewMemberRiskFlagUpdateTask:
    def __init__(self) -> None:
        self.risk_service = RiskService()
        self.batch_size = 8000

        # The cronjob also has a timeout. This is lower so that it ends & logs info gracefully
        self.max_runtime = timedelta(hours=3)

        # stats
        self.num_users_processed: int = 0
        self.num_users_updated: int = 0
        self.num_created_by_risk_name: Dict[str, int] = {}
        self.num_ended_by_risk_name: Dict[str, int] = {}
        self.num_updated_by_risk_name: Dict[str, int] = {}
        self.error_count: int = 0

    def _get_user_ids(self, is_even: Optional[bool] = None) -> Iterator[int]:
        total_count = 0
        # Get Users with an Active Track
        #   since Risks are only meaningful to providers/coaches,
        #   and a Member needs a Track to have a Coach)
        # Todo Filter active users further (User.active doesn't seem very useful)
        last_id = -1
        done = False
        while not done:
            query = db.session.query(MemberTrack.user_id).filter(
                MemberTrack.active == True, MemberTrack.user_id > last_id
            )

            if is_even is not None:
                query = query.filter(MemberTrack.user_id % 2 == (0 if is_even else 1))

            results = (
                query.order_by(MemberTrack.user_id)
                .distinct()
                .limit(self.batch_size)
                .all()
            )

            for item in results:
                last_id = item[0]
                yield item[0]
                total_count += 1
            if len(results) < self.batch_size:
                done = True

        self._log_stats(
            f"MemberRiskFlagUpdateTask total user_ids processed: {total_count}, is_even: {is_even}"
        )

    def _batch(self, user_ids: Iterable[int]) -> Iterable[List[int]]:
        batch = []
        for user_id in user_ids:
            batch.append(user_id)
            if (len(batch)) == self.batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def run(
        self, user_ids: Optional[Iterable[int]] = None, is_even: Optional[bool] = None
    ) -> None:
        start = datetime.utcnow()
        log.info(f"MemberRiskFlagUpdateTask - Starting, is_even {is_even}")
        if not user_ids:
            user_ids = self._get_user_ids(is_even=is_even)

        message = f"MemberRiskFlagUpdateTask - Completed, is_even {is_even}"
        try:
            batch_num = 0
            for batch in self._batch(user_ids):
                batch_num += 1
                self._log_stats(f"Running User Batch {batch_num}, is_even {is_even}")
                self._run_for_user_batch(batch, batch_num, is_even)
                if self.error_count > 5000:
                    message = f"MemberRiskFlagUpdateTask - Aborted Due to Error Count, is_even {is_even}"
                    break
                run_time = datetime.utcnow() - start
                if run_time > self.max_runtime:
                    message = f"MemberRiskFlagUpdateTask - Aborted, Exceeded max runtime, is_even {is_even}"
                    break
        except Exception as e:
            message = f"MemberRiskFlagUpdateTask - Aborted Due to Exception, is_even {is_even}"
            raise e
        finally:
            self._log_stats(message)

    def _run_for_user_batch(
        self, user_ids: List[int], batch_num: int, is_even: Optional[bool] = None
    ) -> None:
        try:
            # Wrap each database query in try-except to handle connection issues
            try:
                health_profile_by_user = self._get_health_profiles(user_ids)
            except Exception as e:
                log.error(
                    f"Error fetching health profiles for batch {batch_num}: {str(e)}, is_even: {is_even}"
                )
                db.session.rollback()
                db.session.remove()
                # If this fails again, let it propagate to the outer try-except
                health_profile_by_user = self._get_health_profiles(user_ids)

            try:
                active_risks_by_user = self._get_active_member_risks(user_ids)
            except Exception as e:
                log.error(
                    f"Error fetching active risks for batch {batch_num}: {str(e)}, is_even: {is_even}"
                )
                db.session.rollback()
                db.session.remove()
                active_risks_by_user = self._get_active_member_risks(user_ids)

            try:
                active_tracks_by_user = self._get_active_member_tracks(user_ids)
            except Exception as e:
                log.error(
                    f"Error fetching active tracks for batch {batch_num}: {str(e)}, is_even: {is_even}"
                )
                db.session.rollback()
                db.session.remove()
                active_tracks_by_user = self._get_active_member_tracks(user_ids)

            for user_id in user_ids:
                try:
                    hp = health_profile_by_user.get(user_id, None)
                    if not hp:
                        continue

                    active_risks = active_risks_by_user.get(user_id, [])
                    active_tracks = active_tracks_by_user.get(user_id, [])

                    # Use savepoint for each user to allow partial rollback
                    try:
                        with db.session.begin_nested():
                            self._run_for_user(user_id, hp, active_risks, active_tracks)

                        db.session.expunge_all()

                    except Exception as e:
                        error_str = str(e)
                        if (
                            "SAVEPOINT" in error_str
                            or "InterfaceError" in error_str
                            or "Can't reconnect until invalid transaction is rolled back"
                            in error_str
                            or "NoneType" in error_str
                        ):
                            log.error(
                                f"_run_for_user_batch {batch_num} connection or transaction error for user {user_id}: {error_str}, is_even: {is_even}"
                            )

                            db.session.rollback()
                            db.session.remove()
                        raise  # Re-raise to be caught by outer try
                except Exception as e:
                    self.error_count += 1

                    log.error(
                        f"_run_for_user_batch {batch_num} failed processing user {user_id}: {str(e)}, is_even: {is_even}",
                        error=str(e),
                        trace=traceback.format_exc(),
                    )

                    # The savepoint will be rolled back, but the outer transaction continues

            db.session.commit()
            self._log_stats(
                f"_run_for_user_batch finished batch {batch_num}, is_even: {is_even}"
            )
        except Exception as e:
            db.session.rollback()
            self._log_stats(
                f"error processing batch {batch_num}: {str(e)}, is_even: {is_even}"
            )
            # Don't raise the exception, just log it and continue with the next batch
            # This prevents one bad batch from stopping the entire process

    def _run_for_user(
        self,
        user_id: int,
        health_profile: HealthProfile,
        active_risks: List[MemberRiskFlag],
        active_tracks: List[str],
    ) -> None:
        self.num_users_processed += 1
        member_risk_service = MemberRiskService(
            user_id,
            health_profile=health_profile,
            modified_reason="MemberRiskFlagUpdateTask",
            risk_service=self.risk_service,  # so that Risk Flag Lookup by name gets cached
            confirm_existing_risks=False,  # don't want existing risks to be modified reach run
            commit=False,
        )
        member_risk_service._set_active_risk_cache(active_risks)

        calc_service = MemberRiskCalcService(member_risk_service, active_tracks)
        result = calc_service.run_all()

        for name in result.risks_added:
            self.num_created_by_risk_name[name] = (
                self.num_created_by_risk_name.get(name, 0) + 1
            )
        for name in result.risks_ended:
            self.num_ended_by_risk_name[name] = (
                self.num_ended_by_risk_name.get(name, 0) + 1
            )
        for name in result.risks_updated:
            self.num_updated_by_risk_name[name] = (
                self.num_updated_by_risk_name.get(name, 0) + 1
            )
        if result.risks_added or result.risks_ended or result.risks_updated:
            self.num_users_updated += 1
        self.error_count += result.error_count

    def _get_health_profiles(self, user_ids: List[int]) -> Dict[int, HealthProfile]:
        try:
            health_profiles: List[HealthProfile] = (
                db.session.query(HealthProfile)
                .filter(HealthProfile.user_id.in_(user_ids))
                .all()
            )
            health_profile_by_user = {}
            for hp in health_profiles:
                health_profile_by_user[hp.user_id] = hp
            return health_profile_by_user
        except Exception as e:
            # If there's a database connection error, log it
            # The outer function will handle retrying
            log.error(f"Error in _get_health_profiles: {str(e)}")
            raise

    def _get_active_member_risks(
        self, user_ids: List[int]
    ) -> Dict[int, List[MemberRiskFlag]]:
        try:
            member_risks: List[MemberRiskFlag] = (
                db.session.query(MemberRiskFlag)
                .filter(MemberRiskFlag.user_id.in_(user_ids))
                .filter(MemberRiskFlag.end.is_(None))
                .options(joinedload(MemberRiskFlag.risk_flag))
                .all()
            )
            member_risks_by_user = defaultdict(list)
            for mr in member_risks:
                member_risks_by_user[mr.user_id].append(mr)
            return member_risks_by_user
        except Exception as e:
            # If there's a database connection error, log it
            # The outer function will handle retrying
            log.error(f"Error in _get_active_member_risks: {str(e)}")
            raise

    def _get_active_member_tracks(self, user_ids: List[int]) -> Dict[int, List[str]]:
        try:
            member_tracks: List[MemberTrack] = (
                db.session.query(MemberTrack)
                .filter(MemberTrack.user_id.in_(user_ids))
                .filter(MemberTrack.active == True)
                .all()
            )
            member_tracks_by_user = defaultdict(list)
            for mt in member_tracks:
                member_tracks_by_user[mt.user_id].append(mt.name)
            return member_tracks_by_user  # type: ignore
        except Exception as e:
            # If there's a database connection error, log it
            # The outer function will handle retrying
            log.error(f"Error in _get_active_member_tracks: {str(e)}")
            raise

    def _log_stats(self, message: str) -> None:
        log.info(
            message,
            context={
                "num_users_processed": self.num_users_processed,
                "num_users_updated": self.num_users_updated,
                "risks_created": self.num_created_by_risk_name,
                "risks_ended": self.num_ended_by_risk_name,
                "risks_updated": self.num_updated_by_risk_name,
            },
        )


@ddtrace.tracer.wrap()
@job("priority")
def update_member_risk_flags_even() -> None:
    if split_cron_in_half_enabled:
        task = NewMemberRiskFlagUpdateTask()
        task.run(is_even=True)


@ddtrace.tracer.wrap()
@job("priority")
def update_member_risk_flags_odd() -> None:
    if split_cron_in_half_enabled:
        task = NewMemberRiskFlagUpdateTask()
        task.run(is_even=False)


@ddtrace.tracer.wrap()
@job("priority")
def update_member_risk_flags() -> None:
    if not split_cron_in_half_enabled:
        MemberRiskFlagUpdateTask().run()

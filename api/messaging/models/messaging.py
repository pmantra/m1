from __future__ import annotations

import enum
from datetime import datetime
from itertools import chain
from typing import Any

import ddtrace
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import backref, load_only, relationship

from authn.models.user import User
from models.base import TimeLoggedModelBase, db
from models.enterprise import UserAssetMessage
from models.profiles import PractitionerProfile
from models.verticals_and_specialties import Vertical, is_cx_vertical_name
from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from services.common import calculate_privilege_type
from utils.data import JSONAlchemy
from utils.log import logger
from utils.mail import send_message
from utils.primitive_threaded_cached_property import primitive_threaded_cached_property

log = logger(__name__)
MONEY_PRECISION = 8  # avoid circular import. TODO move to a separate file


class Channel(TimeLoggedModelBase):
    __tablename__ = "channel"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    comment = Column(JSONAlchemy(Text))
    internal = Column(Boolean, default=False, nullable=False)
    participants = relationship("ChannelUsers")
    messages = relationship(
        "Message", backref="channel", order_by="asc(Message.created_at)"
    )

    def __repr__(self) -> str:
        return f"<Channel[{self.id}]>"

    __str__ = __repr__

    def new_message_ids(self, user_id: int) -> list[int]:
        """
        Return the number of unread messages for the specified user.
        Message author always read their own messages.
        :param user_id:
        :return:
        """
        results = db.session.execute(
            "SELECT m.id, mu.is_read, m.user_id "
            "FROM message m JOIN channel c ON (m.channel_id=c.id) "
            "LEFT JOIN message_users mu ON (mu.message_id=m.id AND mu.user_id = :user_id) "
            "WHERE c.id = :channel_id "
            "AND m.status = 1",
            {"channel_id": self.id, "user_id": user_id},
        )
        new_ids = [
            r[0]
            for r in results.fetchall()
            # unread message: not read and not own message
            if not r[1] and r[2] != user_id
        ]
        return new_ids

    @property
    def has_automated_ca_message(self) -> bool:
        q = Channel.query.filter(
            Channel.messages.any(Message.is_automated_message),
            Channel.id == self.id,
        )
        return db.session.query(q.exists()).scalar()

    @primitive_threaded_cached_property
    def is_wallet(self) -> bool:
        has_wallet_query = """
            SELECT COUNT(*) FROM reimbursement_wallet_users
            WHERE channel_id= :channel_id LIMIT 1;
        """
        return bool(
            db.session.execute(has_wallet_query, {"channel_id": self.id}).scalar()
        )

    @primitive_threaded_cached_property
    def privilege_type(self) -> str:
        return calculate_privilege_type(self.practitioner, self.member)

    # holds a cached practitioner value once it's resolved. if the result is
    # None, the practitioner work will be done again on subsequent calls this is
    # an opportunity for additional optimization.
    _cached_practitioner: User | None = None

    @property
    def practitioner(self) -> User | None:
        # avoid doing the work of resolving the practitioner after the first time
        if self._cached_practitioner:
            return self._cached_practitioner

        channel_users: list[ChannelUsers] = self.participants
        practitioner_users = [p.user for p in channel_users if p.user.is_practitioner]
        if len(practitioner_users) > 1:
            # when participants all have practitioner profiles
            # then the 2nd participant is considered the practitioner
            comment_data: dict = self.comment or {}
            user_id_list = comment_data.get("user_ids")
            if user_id_list and len(user_id_list) >= 2:
                practitioner_id = user_id_list[1]
                practitioner = next(
                    (p.user for p in self.participants if p.user.id == practitioner_id),
                    None,
                )
            else:
                log.error(
                    "Unable to determine practitioner for channel with multiple practitioners",
                    channel=self,
                )
                practitioner = None
        else:
            practitioner = practitioner_users[0] if practitioner_users else None

        self._cached_practitioner = practitioner
        return self._cached_practitioner

    # holds a chached value of the member once it's resolved. if the result is
    # None we will continue to do the look up work on subsequent calls. This is
    # an opportunity for future optimization.
    _cached_member: User | None = None

    @property
    def member(self) -> User | None:
        if self._cached_member:
            return self._cached_member

        channel_users: list[ChannelUsers] = self.participants
        members = [p.user for p in channel_users if p.user.is_member]
        if members:
            self._cached_member = members[0]
            return self._cached_member

        # when participants all have practitioner profiles
        # then the initiator of the channel is considered the member
        comment_data: dict = self.comment or {}
        user_id_list = comment_data.get("user_ids")
        if user_id_list and len(user_id_list) >= 1:
            member_id = user_id_list[0]
            member = next(
                (p.user for p in self.participants if p.user.id == member_id),
                None,
            )
            if member:
                self._cached_member = member
                return self._cached_member

        log.error(
            "Unable to determine member for channel with multiple practitioners",
            channel=self,
        )
        return None

    @property
    def last_message(self) -> Message | None:
        if self.messages:
            return self.messages[-1]
        return None

    @property
    def first_message(self) -> Message | None:
        if self.messages:
            return self.messages[0]
        return None

    def is_active_participant(self, user: User) -> bool:
        return (
            db.session.query(ChannelUsers.id)
            .filter_by(channel=self, user=user, active=True)
            .scalar()
            is not None
        )

    @classmethod
    def participated_by_user(cls, user_id: int) -> list[Channel]:
        return (
            db.session.query(cls)
            .join(ChannelUsers)
            .filter(ChannelUsers.user_id == user_id)
            .order_by(Channel.created_at)
            .all()
        )

    @staticmethod
    def count_unread_channels_for_user(user_id: int) -> int:
        result = db.session.execute(
            """
            SELECT COUNT(DISTINCT m.channel_id) AS unread_channel_count
            FROM message m
            JOIN channel_users cu ON cu.channel_id = m.channel_id
            LEFT JOIN message_users mu ON mu.message_id = m.id AND mu.user_id = :user_id
            WHERE cu.user_id = :user_id
            AND m.status = 1
            AND (mu.is_read IS NULL OR mu.is_read = FALSE)
            AND (m.user_id IS NULL OR m.user_id != :user_id)
            """,
            {"user_id": user_id},
        )

        unread_channel_count = result.scalar() or 0
        return unread_channel_count

    @classmethod
    def get_or_create_channel(
        cls,
        initiator: User,
        users: list[User],
    ) -> Channel:
        # TODO: creation of a new channel should be extracted from the model.
        # Additionally the creation logic must own the act of committing the new channel.
        is_internal = initiator.is_care_coordinator or any(
            u.is_care_coordinator for u in users
        )
        all_parties = [initiator.id] + [u.id for u in users]
        existing_channel = ChannelUsers.find_existing_channel(all_parties)
        # TODO: return early and avoid the additional indent scope
        if existing_channel:
            channel = existing_channel
        else:
            channel = Channel(
                name=" & ".join(
                    [initiator.first_name if initiator.first_name is not None else ""]
                    + [u.first_name for u in users if u.first_name is not None]
                ),
                internal=is_internal,
                comment={"user_ids": all_parties},
            )
            db.session.add(channel)

            participants = [
                ChannelUsers(
                    channel=channel,
                    user_id=initiator.id,
                    is_initiator=True,
                    max_chars=(Message.MAX_CHARS if initiator.is_member else None),
                )
            ]
            for user in users:
                max_chars = Message.MAX_CHARS if user.is_member else None
                participants.append(
                    ChannelUsers(
                        channel=channel,
                        user_id=user.id,
                        is_initiator=False,
                        max_chars=max_chars,
                    )
                )
            db.session.add_all(participants)
            db.session.flush()

        return channel


class ChannelUsers(TimeLoggedModelBase):
    __tablename__ = "channel_users"
    __table_args__ = (UniqueConstraint("channel_id", "user_id"),)
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channel.id"))
    user_id = Column(Integer, ForeignKey("user.id"))
    is_initiator = Column(Boolean, default=False, nullable=False)
    is_anonymous = Column(Boolean, default=False, nullable=False)
    max_chars = Column(Integer, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    channel = relationship("Channel")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ChannelUser[{self.id}]: Channel={self.channel} User={self.user}>"

    __str__ = __repr__

    @staticmethod
    def find_existing_channel(user_ids: list[int]) -> Channel | None:
        """
        Return an existing channel with the same participants if available; Else return None.
        :param user_ids: participants in the channel
        :return:
        """
        sql = """
          SELECT
            cu.channel_id
          FROM
            channel_users cu
          WHERE
            cu.channel_id in 
            (
            -- locate all channel ids that the users participate in
            SELECT
              distinct(cu_inner.channel_id)
            FROM
              channel_users cu_inner
            WHERE
              cu_inner.user_id in ({user_ids})
          )
          -- Count the number of participants in each of the channels 
          -- returned by the subquery. Ensure it matches the number of 
          -- user_ids we expect
          GROUP BY cu.channel_id
          HAVING count(cu.channel_id) = {num_participants}
          -- for each channel_user row validate the user_id exists 
          -- in our expected list of ids. 
          AND SUM(CASE WHEN cu.user_id NOT IN ({user_ids}) THEN 1 ELSE 0 END) = 0
        """.format(
            num_participants=len(user_ids),
            user_ids=",".join(str(uid) for uid in user_ids),
        )

        results = db.session.execute(sql)
        row = results.fetchone()
        # TODO: return early and avoid the additional indent scope
        if row:
            return Channel.query.get(row[0])
        else:
            return None


class MessageSourceEnum(enum.Enum):
    PROMOTE_MESSAGING = "promote_messaging"


class Message(TimeLoggedModelBase):
    __tablename__ = "message"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    channel_id = Column(Integer, ForeignKey("channel.id"))
    body = Column(Text)
    status = Column(Boolean, default=True, nullable=False)
    zendesk_comment_id = Column(BigInteger, unique=True)
    braze_campaign_id = Column(String(36), default=None, nullable=True)
    braze_dispatch_id = Column(String(36), default=None, nullable=True)
    availability_notification_request_id = Column(
        Integer,
        ForeignKey("availability_notification_request.id"),
        nullable=True,
    )
    # author user
    user = relationship("User")
    # all users who see this message
    # note MessageUsers are created lazily by calls to mark read and acknowledged
    message_users = relationship("MessageUsers", lazy="selectin")
    source = Column(String(64), default=None, nullable=False)

    _attachments = relationship(
        "UserAssetMessage",
        order_by="UserAssetMessage.position",
        collection_class=ordering_list("position"),
    )
    attachments = association_proxy(
        "_attachments", "user_asset", creator=lambda f: UserAssetMessage(user_asset=f)
    )

    MAX_CHARS: int = 4096

    def __repr__(self) -> str:
        return f"<Message[{self.id}]: Status={self.status} Channel={self.channel} User={self.user}>"

    __str__ = __repr__

    def message_user_with_id(self, user_id: int) -> MessageUsers | None:
        return next((mu for mu in self.message_users if mu.user_id == user_id), None)

    def is_read_by(self, user_id: int) -> bool:
        """
        Getter for is_read flag per user.
        Message author always read their own messages.
        :param user_id:
        :return: bool
        """
        if self.user_id == user_id:
            return True

        target_user = self.message_user_with_id(user_id)
        if not target_user:
            return False
        return target_user.is_read

    def is_acknowledged_by(self, user_id: int) -> bool:
        """
        Getter for is_acknowledged flag per user
        :param user_id:
        :return: bool
        """
        target_user = self.message_user_with_id(user_id)
        if not target_user:
            return False
        return target_user.is_acknowledged

    def mark_as_read_by(self, user_id: int) -> None:
        """
        Setter for is_read flag per user.
        Session needs to be committed explicitly to be effective.
        """
        target_user = self.message_user_with_id(user_id)
        if not target_user:
            target_user = MessageUsers(
                message_id=self.id,
                user_id=user_id,
            )
        # mark as read
        target_user.is_read = True
        db.session.add(target_user)

    def mark_as_acknowledged_by(self, user_id: int) -> None:
        """
        Setter for is_acknowledged flag per user.
        :param user_id:
        """
        target_user = self.message_user_with_id(user_id)
        if not target_user:
            target_user = MessageUsers(
                message_id=self.id,
                user_id=user_id,
            )
        target_user.is_acknowledged = True
        db.session.add(target_user)

    @property
    def meta(self) -> list[dict[str, int | bool]]:
        """
        Helper function to show message meta data per user
        to facilitate MessageUsersSchema for object to json conversion.
        """
        ret = []
        for participant in self.channel.participants:
            participant_id = participant.user.id
            ret.append(
                {
                    "user_id": participant_id,
                    "is_read": self.is_read_by(participant_id),
                    "is_acknowledged": self.is_acknowledged_by(participant_id),
                }
            )
        return ret

    @property
    def is_first_message_in_channel(self) -> bool:
        return self.channel.first_message == self

    @property
    def requires_fee(self) -> bool:
        # TODO: why dont we have here the check for @mavenclinic here
        if self.channel.practitioner.is_care_coordinator:
            log.info(
                "Message for care coordinator, does not require fee.",
                message_id=self.id,
            )
            return False

        prac_id = self.channel.practitioner.id
        prac_profile = self.channel.practitioner.practitioner_profile
        message_id = self.id
        prac_is_staff = prac_profile.is_staff

        prac_active_contract = prac_profile.active_contract
        if not prac_active_contract:
            # Notify Provider Ops that practitioner has no contract
            notification_title = "Provider has no active contract"
            notification_text = (
                f"Provider [{prac_id}] has no active contract.\n"
                f"Message {message_id} has been sent, but the provider has no active contract, so it's unclear if a fee should be generated.\n"
                f"For now, we are falling back to using the provider's is_staff value, which is {prac_is_staff}, "
                f"so a fee will {'not ' if prac_is_staff else ''}be generated for the message.\n"
                "Please set an active contract for this provider."  # Add 'and alert engineering if a fee needs to be created.' when fallback to is_staff is removed
            )

            send_message(
                to_email=PROVIDER_CONTRACTS_EMAIL,
                subject=notification_title,
                text=notification_text,
                internal_alert=True,
                production_only=True,
            )
            # DD log monitor: https://app.datadoghq.com/monitors/121681314
            log.warning(
                notification_title,
                practitioner_id=prac_id,
                message_id=message_id,
                prac_is_staff=prac_is_staff,
            )
            # Fallback to using is_staff to decide if generating a fee (which means do nothing else in this if statement given that the is_staff check is down the road)
            # Note: fallback to be deprecated once is_staff is deprecated
        else:
            # If contract emits_fee is inconsistent with is_staff, notify Provider Ops and fallback to is_staff
            # Note: fallback to be deprecated once is_staff is deprecated
            if prac_active_contract.emits_fees == prac_profile.is_staff:
                notification_title = (
                    "Provider active contract inconsistent with is_staff value"
                )
                notification_text = (
                    f"Provider [{prac_id}] active contract [{prac_active_contract.id}] is of type {prac_active_contract.contract_type.value}, "
                    f"but their is_staff value is {prac_is_staff}, which is inconsistent for that contract type.\n"
                    f"Message {message_id} has been completed and we need the provider's active contract to decide if a fee should be generated.\n"
                    "Given this inconsistency, we are falling back to using the provider's is_staff value, "
                    f"so a fee will {'not ' if prac_is_staff else ''}be generated for the message.\n"
                    "Please update either the is_staff value or the contract type for this provider to make them consistent."  # Add 'and alert engineering if a fee needs to be created.' when fallback to is_staff is removed
                )

                send_message(
                    to_email=PROVIDER_CONTRACTS_EMAIL,
                    subject=notification_title,
                    text=notification_text,
                    internal_alert=True,
                    production_only=True,
                )
                # DD log monitor: https://app.datadoghq.com/monitors/121685718
                log.warning(
                    notification_title,
                    practitioner_id=prac_id,
                    message_id=message_id,
                    prac_is_staff=prac_is_staff,
                    contract_type=prac_active_contract.contract_type.value,
                )
            else:  # This is the happy path (practitioner contract exists and is consistent with is_staff)
                active_contract_emits_fee = prac_active_contract.emits_fees
                log.info(
                    "Correctly using active_contract.emits_fee to decide if Message fee should be generated",
                    practitioner_id=prac_id,
                    message_id=message_id,
                    prac_is_staff=prac_is_staff,
                    contract_type=prac_active_contract.contract_type.value,
                    active_contract_emits_fee=active_contract_emits_fee,
                )
                return active_contract_emits_fee

        # Fallback
        if self.channel.practitioner.practitioner_profile.is_staff:
            log.info(
                "Message for staff provider, does not require fee.", message_id=self.id
            )
            return False

        return True

    @classmethod
    def retain_data_for_user(cls, user: User) -> bool:
        return any(
            # Retain if user (or a non care coordinator) authored any of the messages from the channels they belong to.
            m.user_id == user.id or not m.user.is_care_coordinator
            for m in chain.from_iterable(
                c.messages for c in Channel.participated_by_user(user.id)
            )
        )

    @hybrid_property
    def is_automated_message(self) -> bool:
        return self.braze_campaign_id is not None

    @is_automated_message.expression  # type: ignore[no-redef]
    def is_automated_message(cls):
        return cls.braze_campaign_id != None

    @classmethod
    def last_ca_message_to_member(cls, user: User) -> Message | None:
        return (
            cls.query.options(load_only("created_at"))
            .join(Message.user)
            .join(User.practitioner_profile)
            .join(PractitionerProfile.verticals)
            .filter(
                # Message from CA...
                is_cx_vertical_name(Vertical.name),
                # ... in a channel with user participant.
                cls.channel_id.in_(
                    db.session.query(Channel.id)
                    .join(Channel.participants)
                    .filter(ChannelUsers.user == user)
                    .subquery()
                ),
            )
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def last_member_message_to_ca(cls, user: User) -> Message | None:
        return (
            cls.query.options(load_only("created_at"))
            .join(Channel)
            .join(Channel.participants)
            .join(User.practitioner_profile)
            .join(PractitionerProfile.verticals)
            .filter(
                # Message from user...
                cls.user == user,
                # ... in a channel with CA participant.
                is_cx_vertical_name(Vertical.name),
            )
            .order_by(cls.created_at.desc())
            .first()
        )


class MessageUsers(TimeLoggedModelBase):
    """
    Models to store a message's per user properties. read / like etc.
    """

    __tablename__ = "message_users"
    message_id = Column(Integer, ForeignKey("message.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    is_read = Column(Boolean, default=False, nullable=False)
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    message = relationship("Message", backref="audiences")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<MessageUsers: Message={self.message} User={self.user} is_read={self.is_read} is_acknowledged={self.is_acknowledged}>"

    __str__ = __repr__


class MessageProduct(TimeLoggedModelBase):
    __tablename__ = "message_product"
    id = Column(Integer, primary_key=True)
    number_of_messages = Column(Integer, nullable=False)
    price = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<MessageProduct[{self.id}] {self.number_of_messages} message for {self.price}>"

    __str__ = __repr__


class MessageBilling(TimeLoggedModelBase):
    __tablename__ = "message_billing"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    message_product_id = Column(Integer, ForeignKey("message_product.id"))
    stripe_id = Column(String(190), index=True)
    json = Column(JSONAlchemy(Text), default={})

    user = relationship("User")
    message_product = relationship("MessageProduct")

    def __repr__(self) -> str:
        return f"<MessageBilling[{self.id}] User={self.user} MessageProduct={self.message_product}>"

    __str__ = __repr__

    @classmethod
    @ddtrace.tracer.wrap()
    def create(cls, **kwargs: Any) -> MessageBilling:
        billing = cls(
            user_id=kwargs.get("user_id"),
            message_product_id=kwargs.get("message_product_id"),
            stripe_id=kwargs.get("stripe_id"),
            json=kwargs.get("json"),
        )
        db.session.add(billing)
        db.session.flush()
        return billing

    @property
    def staff_cost(self) -> float | None:
        return (self.json or {}).get("staff_cost")

    @staff_cost.setter
    def staff_cost(self, val: float | None) -> None:
        self.json["staff_cost"] = val


class MessageCredit(TimeLoggedModelBase):
    """
    A de-normalized record keeping table that stores available credit
    allowances, usages and other meta data about messages.
    Each row that has no message_id represents an unused message credit;
    Each row that has message_id represents an used message credit.
    The oldest message credit would be applied upon consumption.
    """

    __tablename__ = "message_credit"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    message_billing_id = Column(
        Integer, ForeignKey("message_billing.id"), nullable=True
    )
    # Plan Segment is Deprecated
    plan_segment_id = 0
    message_id = Column(Integer, ForeignKey("message.id"), nullable=True)
    respond_by = Column(DateTime(), nullable=True, index=True)
    responded_at = Column(DateTime(), nullable=True)
    response_id = Column(Integer, ForeignKey("message.id"), nullable=True)
    refunded_at = Column(DateTime(), nullable=True)
    json = Column(JSONAlchemy(Text), default={})

    user = relationship("User", backref="message_credits")
    message = relationship(
        "Message", foreign_keys=message_id, backref=backref("credit", uselist=False)
    )
    message_billing = relationship("MessageBilling", backref="message_credits")
    response = relationship("Message", foreign_keys=response_id)

    def __repr__(self) -> str:
        return (
            f"<MessageCredit[{self.id}]: User={self.user} MessageId={self.message_id}>"
        )

    __str__ = __repr__

    @classmethod
    def create(
        cls,
        count: int = 1,
        **kwargs: Any,
    ) -> list[MessageCredit]:
        credits = [
            MessageCredit(
                user_id=kwargs.get("user_id"),
                message_billing_id=kwargs.get("message_billing_id"),
                message_id=kwargs.get("message_id"),
                respond_by=kwargs.get("respond_by"),
                responded_at=kwargs.get("responded_at"),
                response_id=kwargs.get("response_id"),
                json=kwargs.get("json"),
                created_at=kwargs.get("created_at"),
                modified_at=kwargs.get("modified_at"),
            )
            for _ in range(count)
        ]
        db.session.add_all(credits)
        db.session.flush()
        return credits

    def is_eligible_for_refund(self) -> bool:
        """
        Determines if the MessageCredit can be refunded.
        """
        now = datetime.utcnow()
        if self.refunded_at:
            log.warning(
                "Message credit has already been refunded",
                message_credit_id=self.id,
                user_id=self.user.id,
            )
            return False
        # if we promised to respond by a time and it is after that time
        # then a refund may be issued
        return self.respond_by is not None and self.respond_by < now

    def refund(self) -> None:
        """
        Refund the current message credit.
        Checking the response window logic should be done prior to this.
        """
        if not self.is_eligible_for_refund():
            return None

        now = datetime.utcnow()
        self.refunded_at = now
        new = self.__class__(
            user_id=self.user.id,
            message_billing_id=self.message_billing_id,
            json={"refunded_from_id": self.id},
        )
        db.session.add_all([self, new])
        db.session.flush()
        log.debug(
            "Message credit refunded",
            new_credit_id=new.id,
            parent_credit_id=self.id,
        )
        return None

    @classmethod
    @ddtrace.tracer.wrap()
    def first_unused_credit_for_user(cls, user: User) -> MessageCredit | None:
        """
        Find the oldest unused message credit for a user.
        """
        query = MessageCredit.query.filter(
            MessageCredit.user_id == user.id,
            MessageCredit.message_id.is_(None),
        ).order_by(MessageCredit.created_at.asc())

        return query.first()

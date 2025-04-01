from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from appointments.models.appointment_ack import AppointmentAck


class MemberAppointmentAck(AppointmentAck):
    __tablename__ = "member_appointment_ack"

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", uselist=False)

    ack_date = Column(DateTime(), nullable=True)

    confirm_message_sid = Column(String(50), nullable=True)
    reply_message_sid = Column(String(50), nullable=True)

    sms_sent_at = Column(DateTime(), nullable=True)

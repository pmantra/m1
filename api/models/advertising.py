from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from utils.data import JSONAlchemy

from .base import TimeLoggedModelBase


class ATTRIBUTION_ID_TYPES:
    apple_ifa = "apple_ifa"


class UserInstallAttribution(TimeLoggedModelBase):
    __tablename__ = "user_install_attribution"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, unique=True)
    device_id = Column(String(50), unique=True)
    id_type = Column(
        Enum(*[ATTRIBUTION_ID_TYPES.apple_ifa], name="id_type"),
        nullable=False,
        default=ATTRIBUTION_ID_TYPES.apple_ifa,
    )
    json = Column(JSONAlchemy(Text))

    def __repr__(self) -> str:
        return (
            f"<UserInstallAttribution [User {self.user_id} (Device {self.device_id})]>"
        )

    __str__ = __repr__

    @property
    def source_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.json.get("media_source", "Organic")

    @property
    def install_info(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = self.json or {}
        source = data.get("media_source")

        export = {"install_source": source}
        if data.get("registered_on_web"):
            export["install_campaign"] = data.get("install_campaign")
            export["install_content"] = data.get("install_content")
            export["install_ad_unit"] = data.get("install_ad_unit")
        elif source == "Facebook Ads":
            export["install_campaign"] = data.get("fb_campaign_name")
            export["install_ad_unit"] = data.get("fb_adgroup_name")
            export["install_content"] = data.get("fb_adset_name")
        elif source:
            export["install_campaign"] = data.get("campaign")
            export["install_content"] = data.get("af_sub1")
            export["install_ad_unit"] = data.get("af_sub2")

        return export


class AutomaticCodeApplication(TimeLoggedModelBase):
    __tablename__ = "automatic_code_application"

    id = Column(Integer, primary_key=True)
    install_campaign = Column(String(190), unique=True)

    referral_code_id = Column(Integer, ForeignKey("referral_code.id"), nullable=False)
    code = relationship("ReferralCode", backref="automatic_uses")

    def __repr__(self) -> str:
        return f"<AutomaticCodeApplication [install_campaign={self.install_campaign} (referral_code={self.referral_code_id})]>"

    __str__ = __repr__

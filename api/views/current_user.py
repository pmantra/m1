from dataclasses import asdict, dataclass

import ddtrace

from common.services.api import PermissionedUserResource
from utils import security


@dataclass
class UserResponse:
    id: int
    email: str
    first_name: str
    middle_name: str
    last_name: str
    name: str
    username: str
    date_of_birth: str
    role: str
    onboarding_state: str
    avatar_url: str
    image_url: str
    image_id: int
    esp_id: str
    encoded_id: str
    mfa_state: str
    sms_phone_number: str
    bright_jwt: str  # deprecated


class CurrentUserResource(PermissionedUserResource):
    @ddtrace.tracer.wrap()
    def get(self) -> dict:
        return asdict(
            UserResponse(
                id=self.user.id,
                email=self.user.email,
                first_name=self.user.first_name,
                middle_name=self.user.middle_name,
                last_name=self.user.last_name,
                name=self.user.full_name,
                username=self.user.username,
                date_of_birth=self.user.health_profile.birthday.isoformat()
                if self.user.health_profile and self.user.health_profile.birthday
                else None,
                role=self.user.role_name or "",
                onboarding_state=self.user.onboarding_state.state.value
                if self.user.onboarding_state
                else None,
                avatar_url=self.user.avatar_url,
                image_url=self.user.avatar_url,
                image_id=self.user.image_id,
                esp_id=self.user.esp_id,
                encoded_id=security.new_user_id_encoded_token(self.user.id),
                mfa_state=self.user.mfa_state.value,
                sms_phone_number=self.user.sms_phone_number,
                bright_jwt="",
            )
        )

from __future__ import annotations

import enum
from dataclasses import dataclass

HEARTBEAT_CONNECTION_INTERVAL_DEFAULT = 5000
HEARTBEAT_CONNECTION_INTERVAL_FLAG = "configure-video-heartbeat-interval"
HEARTBEAT_CONNECTION_PATH = "/api/v1/video/connection/{appointment_api_id}/heartbeat"


class AppointmentConnectionType(str, enum.Enum):
    # for now this is the only connection type we are supporting
    VIDEO = "video"


class VideoPlatform(str, enum.Enum):
    ZOOM = "zoom"
    VONAGE = "vonage"


@dataclass
class AppointmentConnectionClientInfo:
    capabilities: list[VideoPlatform] | None = None
    device_type: str | None = None
    connection_stats: dict | None = None


@dataclass
class AppointmentConnectionResponse:
    heartbeat: HeartbeatConnectionSchema | None = None
    launch_configuration: LaunchConfigurationSchema | None = None


@dataclass
class LaunchConfigurationSchema:
    connection_type: AppointmentConnectionType
    video_platform: VideoPlatform
    session_id: str
    token: str
    api_key: str | None = None


@dataclass
class HeartbeatConnectionSchema:
    period_millis: int
    heartbeat_path: str

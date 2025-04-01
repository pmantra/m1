import datetime
import enum
import os

# Indicia
INDICIA_DOWNLOAD_PATH = "/Maven/milk-outgoing-status"
FTP_USERNAME = os.environ.get("INDICIA_USERNAME")
FTP_PASSWORD = os.environ.get("INDICIA_PASSWORD")
FTP_HOST = os.environ.get("INDICIA_HOST")


class BMSProductNames(enum.Enum):
    BMS_PUMP_AND_CARRY = "pump_and_carry"
    BMS_PUMP_AND_CHECK = "pump_and_check"
    BMS_PUMP_AND_POST = "pump_and_post"


INDICIA_ITEM_NUMBERS = {
    BMSProductNames.BMS_PUMP_AND_POST.value: "2-85228-K",
    BMSProductNames.BMS_PUMP_AND_CARRY.value: "S-21606-K",
    BMSProductNames.BMS_PUMP_AND_CHECK.value: "231564-K",
}

# BMS logic
BMS_SHIPPING_BUSINESS_DAYS = 5


SHIPPING_BLACKOUT_DATES = frozenset(
    (
        datetime.date(2023, 12, 25),
        datetime.date(2023, 12, 26),
        datetime.date(2024, 1, 1),
        datetime.date(2024, 1, 2),
        datetime.date(2024, 1, 15),
        datetime.date(2024, 2, 19),
        datetime.date(2024, 4, 8),
        datetime.date(2024, 4, 9),
        datetime.date(2024, 5, 27),
        datetime.date(2024, 6, 19),
        datetime.date(2024, 9, 2),
        datetime.date(2024, 11, 28),
        datetime.date(2024, 11, 29),
        datetime.date(2024, 12, 2),
        datetime.date(2024, 12, 24),
        datetime.date(2024, 12, 25),
        datetime.date(2024, 12, 26),
        datetime.date(2025, 1, 1),
        datetime.date(2025, 1, 2),
        datetime.date(2025, 1, 20),
        datetime.date(2025, 1, 21),
        datetime.date(2025, 2, 17),
        datetime.date(2025, 2, 18),
        datetime.date(2025, 5, 26),
        datetime.date(2025, 5, 27),
        datetime.date(2025, 6, 19),
        datetime.date(2025, 7, 4),
        datetime.date(2025, 9, 1),
        datetime.date(2025, 9, 2),
        datetime.date(2025, 11, 27),
        datetime.date(2025, 11, 28),
        datetime.date(2025, 12, 1),
        datetime.date(2025, 12, 24),
        datetime.date(2025, 12, 25),
        datetime.date(2025, 12, 26),
        datetime.date(2025, 12, 31),
    )
)

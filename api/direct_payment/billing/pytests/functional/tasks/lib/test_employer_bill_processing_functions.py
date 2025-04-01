import datetime

import pytest

from direct_payment.billing.constants import ORG_ID_AMAZON, ORG_ID_OHIO
from direct_payment.billing.models import PayorType
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.billing.tasks.lib.employer_bill_processing_functions import (
    can_employer_bill_be_auto_processed,
    can_employer_bill_be_processed,
)
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory

T_MINUS_1 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=-1)
T_PLUS_1 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)


class TestEmployerProcessingFunctions:
    @pytest.mark.parametrize(
        ids=[
            "1. Payor type MEMBER",
            "2. Payor type CLINIC",
        ],
        argnames="payor_type",
        argvalues=[PayorType.MEMBER, PayorType.CLINIC],
    )
    def test_can_employer_bill_be_auto_processed_error(self, payor_type):
        with pytest.raises(ValueError):
            can_employer_bill_be_auto_processed(
                BillFactory.build(payor_type=payor_type)
            )

    @pytest.mark.parametrize(
        ids=[
            "01. Feature Flag True, processing_scheduled_at_or_after None, expected False",
            "02. Feature Flag True, processing_scheduled_at_or_after Future, expected False",
            "03. Feature Flag True, processing_scheduled_at_or_after Past, expected True",
            "07. Feature Flag True, org Ohio processing_scheduled_at_or_after None, expected False",
            "08. Feature Flag True, org Ohio processing_scheduled_at_or_after Future, expected False",
            "09. Feature Flag True, org Ohio processing_scheduled_at_or_after Past, expected False",
            "10. Feature Flag True, org Amazon processing_scheduled_at_or_after None, expected False",
            "11. Feature Flag True, org Amazon processing_scheduled_at_or_after Future, expected False",
            "12. Feature Flag True, org Amazon processing_scheduled_at_or_after Past, expected False",
        ],
        argnames="processing_scheduled_at_or_after, inp_org_id, exp",
        argvalues=[
            (None, 1, False),
            (T_PLUS_1, 1, False),
            (T_MINUS_1, 1, True),
            (None, ORG_ID_OHIO, False),
            (T_PLUS_1, ORG_ID_OHIO, False),
            (T_MINUS_1, ORG_ID_OHIO, False),
            (None, ORG_ID_AMAZON, False),
            (T_PLUS_1, ORG_ID_AMAZON, False),
            (T_MINUS_1, ORG_ID_AMAZON, False),
        ],
    )
    def test_can_employer_bill_be_auto_processed(
        self, processing_scheduled_at_or_after, inp_org_id, exp
    ):
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=inp_org_id
        )
        res = can_employer_bill_be_auto_processed(
            BillFactory.build(
                payor_type=PayorType.EMPLOYER,
                processing_scheduled_at_or_after=processing_scheduled_at_or_after,
                payor_id=ros.id,
            ),
        )
        assert res == exp

    @pytest.mark.parametrize(
        ids=[
            "01. Feature Flag True, processing_scheduled_at_or_after None, expected False",
            "02. Feature Flag True, processing_scheduled_at_or_after Future, expected False",
            "03. Feature Flag True, processing_scheduled_at_or_after Past, expected True",
            "07. Feature Flag True, org Ohio processing_scheduled_at_or_after None, expected False",
            "08. Feature Flag True, org Ohio processing_scheduled_at_or_after Future, expected False",
            "09. Feature Flag True, org Ohio processing_scheduled_at_or_after Past, expected True",
            "10. Feature Flag True, org Amazon processing_scheduled_at_or_after None, expected False",
            "11. Feature Flag True, org Amazon processing_scheduled_at_or_after Future, expected False",
            "12. Feature Flag True, org Amazon processing_scheduled_at_or_after Past, expected True",
        ],
        argnames="processing_scheduled_at_or_after, inp_org_id, exp",
        argvalues=[
            (None, 1, False),
            (T_PLUS_1, 1, False),
            (T_MINUS_1, 1, True),
            (None, ORG_ID_OHIO, False),
            (T_PLUS_1, ORG_ID_OHIO, False),
            (T_MINUS_1, ORG_ID_OHIO, True),
            (None, ORG_ID_AMAZON, False),
            (T_PLUS_1, ORG_ID_AMAZON, False),
            (T_MINUS_1, ORG_ID_AMAZON, True),
        ],
    )
    def test_can_employer_bill_be_processed(
        self, processing_scheduled_at_or_after, inp_org_id, exp
    ):
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=inp_org_id
        )
        res = can_employer_bill_be_processed(
            BillFactory.build(
                payor_type=PayorType.EMPLOYER,
                processing_scheduled_at_or_after=processing_scheduled_at_or_after,
                payor_id=ros.id,
            ),
        )
        assert res == exp

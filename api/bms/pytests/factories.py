import datetime

import factory

from bms.models.bms import BMSOrder, BMSProduct, BMSShipment, BMSShipmentProducts
from conftest import BaseMeta
from pytests.factories import AddressFactory, EnterpriseUserFactory

SQLAlchemyModelFactory = factory.alchemy.SQLAlchemyModelFactory


class BMSProductFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = BMSProduct


class BMSOrderFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = BMSOrder

    travel_start_date = datetime.datetime.today()
    travel_end_date = datetime.datetime.today() + datetime.timedelta(days=15)
    user = factory.SubFactory(EnterpriseUserFactory)


class BMSShipmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = BMSShipment

    recipient_name = "Tester One"
    address = factory.SubFactory(AddressFactory)
    tel_number = "123456789"
    tel_region = "1"


class BMSShipmentProductsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = BMSShipmentProducts

    bms_shipment = factory.SubFactory(BMSShipmentFactory)
    bms_product = factory.SubFactory(BMSProductFactory)
    quantity = 1

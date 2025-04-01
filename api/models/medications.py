from sqlalchemy import Column, String

from models.base import ModelBase


class Medication(ModelBase):
    # This isn't actually a primary key (though it could be!). SQLAlchemy just
    # won't let you create a model for a table without one.
    product_id = Column(String, primary_key=True)
    product_ndc = Column(String)
    product_type_name = Column(String)
    proprietary_name = Column(String, nullable=False)
    proprietary_name_suffix = Column(String)
    nonproprietary_name = Column(String, nullable=False)
    dosage_form_name = Column(String)
    route_name = Column(String)
    labeler_name = Column(String)
    substance_name = Column(String)
    pharm_classes = Column(String)
    dea_schedule = Column(String)
    listing_record_certified_through = Column(String)

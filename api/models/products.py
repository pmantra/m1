import enum
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import relationship

from models import base
from storage.connection import db
from utils.log import logger

if TYPE_CHECKING:
    from authn.models.user import User

log = logger(__name__)

MONEY_PRECISION = 8


class Purposes(enum.Enum):
    BIRTH_PLANNING = "birth_planning"
    BIRTH_NEEDS_ASSESSMENT = "birth_needs_assessment"
    POSTPARTUM_NEEDS_ASSESSMENT = "postpartum_needs_assessment"
    INTRODUCTION = "introduction"
    INTRODUCTION_EGG_FREEZING = "introduction_egg_freezing"
    INTRODUCTION_FERTILITY = "introduction_fertility"
    CHILDBIRTH_EDUCATION = "childbirth_ed"
    PEDIATRIC_PRENATAL_CONSULT = "pediatric_prenatal_consult"
    POSTPARTUM_PLANNING = "postpartum_planning"


class Product(base.TimeLoggedModelBase):
    __tablename__ = "product"
    constraints = (UniqueConstraint("user_id", "minutes", "price", "vertical_id"),)

    id = Column(Integer, primary_key=True)
    is_active = Column(Boolean, default=True, nullable=False)
    vertical_id = Column(Integer, ForeignKey("vertical.id"))
    vertical = relationship("Vertical")
    description = Column(String(280))
    minutes = Column(Integer)
    price = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))
    purpose = Column(Enum(Purposes))
    user_id = Column(Integer, ForeignKey("user.id"))
    practitioner = relationship("User", backref="products")
    prep_buffer = Column(Integer)

    def __repr__(self) -> str:
        return f"<Product {self.id} [{self.minutes} mins - ${self.price}]>"

    __str__ = __repr__

    @staticmethod
    def sort_products_by_price(products: List["Product"]) -> None:
        """
        Sort the given list of products in-place.
        This can be used to determine which product is a provider's default product.
        See /v1/products for the logic this needs to mimic. Frontend uses the 1st product from that.

        Products are prioritized by:
            - lowest price; if tied then use:
            - shortest duration; if tied then use:
            - smallest id
        """
        return products.sort(key=lambda p: (p.price, p.minutes, p.id))


def add_products(practitioner: "User") -> None:
    verticals = practitioner.practitioner_profile.verticals

    if not verticals:
        return

    for vertical in verticals:
        for product in vertical.products:
            if next(
                (
                    p
                    for p in practitioner.products
                    if p.vertical == vertical and p.minutes == product["minutes"]
                ),
                False,
            ):
                log.debug(
                    "Product already exists for practitioner",
                    minutes=product["minutes"],
                    practitioner_id=practitioner.id,
                )
                continue
            else:
                new = Product(
                    minutes=product["minutes"],
                    vertical=vertical,
                    price=product["price"],
                    practitioner=practitioner,
                    purpose=product.get("purpose"),
                )
                db.session.add(new)
                log.debug("Adding %s for %s", new, practitioner)

    db.session.commit()
    log.debug("Added products for %s", practitioner)

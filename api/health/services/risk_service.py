from typing import Dict, Iterable, List, Optional, Union

from health.data_models.risk_flag import RiskFlag
from health.models.risk_enums import RiskFlagName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class RiskService:
    def __init__(self) -> None:
        # cache risks already retrieved
        self._by_name: Dict[str, Optional[RiskFlag]] = {}

    def get_by_name(self, name: Union[str, RiskFlagName]) -> Optional[RiskFlag]:
        if isinstance(name, RiskFlagName):
            name = name.value

        if name in self._by_name:
            return self._by_name[name]

        risk_flag = (
            db.session.query(RiskFlag).filter(RiskFlag.name == name).one_or_none()
        )
        if risk_flag is None:
            log.error("Risk Flag not found", risk_flag=name)
        self._by_name[name] = risk_flag
        return risk_flag

    def get_by_id(self, id: int) -> RiskFlag:
        return db.session.query(RiskFlag).filter(RiskFlag.id == id).one()

    def get_all_by_id(self, ids: Iterable[int]) -> List[RiskFlag]:
        risk_flags = db.session.query(RiskFlag).filter(RiskFlag.id.in_(ids)).all()
        return risk_flags

    def get_all_names(self) -> List[str]:
        names = [i[0] for i in db.session.query(RiskFlag.name).all()]
        names.sort()
        return names

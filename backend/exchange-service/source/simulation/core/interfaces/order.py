from abc import ABC, abstractmethod
from decimal import Decimal
from source.simulation.core.enums.side import Side


class Order_ABC(ABC):
    @abstractmethod
    def get_original_qty(self) -> float:
        pass

    @abstractmethod
    def get_remaining_qty(self) -> float:
        pass

    @abstractmethod
    def get_completed_qty(self) -> float:
        pass

    @abstractmethod
    def get_price(self) -> Decimal:
        pass

    @abstractmethod
    def get_cl_ord_id(self) -> str:
        pass

    @abstractmethod
    def get_side(self) -> Side:
        pass

    @abstractmethod
    def get_order_id(self) -> str:
        pass

    @abstractmethod
    def get_order_fill_rate(self) -> float:
        pass

    @abstractmethod
    def get_order_type(self) -> str:
        pass
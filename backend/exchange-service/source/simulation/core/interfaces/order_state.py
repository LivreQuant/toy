from abc import ABC, abstractmethod


class OrderState_ABC(ABC):
    @abstractmethod
    def get_order_id(self) -> str:
        pass

    @abstractmethod
    def get_leaves_qty(self) -> float:
        pass

    @abstractmethod
    def get_qty(self) -> float:
        pass

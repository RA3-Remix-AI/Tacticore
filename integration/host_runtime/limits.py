"""Hard execution budgets, independent from model soft style preferences."""
from dataclasses import asdict, dataclass

from .contracts import ContractError, integer, object_fields


@dataclass(frozen=True)
class ExecutionLimits:
    production_total_budget: int = 2000
    reserve_floor: int = 1500
    max_command_budget: int = 1000

    def __post_init__(self):
        integer(self.production_total_budget, 1, 20000, 'invalid_production_total_budget')
        integer(self.reserve_floor, 50, 10000, 'invalid_reserve_floor')
        integer(self.max_command_budget, 1, 1000, 'invalid_command_budget')
        if self.max_command_budget > self.production_total_budget:
            raise ContractError('command_budget_exceeds_total')

    @classmethod
    def from_dict(cls, value):
        return cls(**object_fields(value, set(cls.__dataclass_fields__)))

    def public(self):
        return asdict(self)

from dataclasses import dataclass
from typing import Optional, Tuple, Union


@dataclass(frozen=True)
class RGBA:
    r: int
    g: int
    b: int
    a: int = 255

    def __iter__(self):
        yield self.r
        yield self.g
        yield self.b
        yield self.a

    def to_tuple(self):
        return (self.r, self.g, self.b, self.a)


@dataclass(frozen=True)
class RuleArguments:
    rule_type: str
    channel: str
    initial_value: bool
    show_on_true: bool
    visMin: Optional[Union[int, float, str]]
    visMax: Optional[Union[int, float, str]]
    # (min, max) ranges: a range rule shown on true also holds while the value
    # is in none of them (an EDM symbol's state 0, which shows when no state matches).
    or_outside: Optional[Tuple[Tuple[Union[int, float, str], Union[int, float, str]], ...]] = None

    def __iter__(self):
        yield self.rule_type
        yield self.channel
        yield self.initial_value
        yield self.show_on_true
        yield self.visMin
        yield self.visMax
        yield self.or_outside

    def to_tuple(self):
        return (
            self.rule_type,
            self.channel,
            self.initial_value,
            self.show_on_true,
            self.visMin,
            self.visMax,
            self.or_outside,
        )

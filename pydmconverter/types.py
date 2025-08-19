from dataclasses import dataclass


@dataclass(frozen=True)
class RGBA:
    r: int
    g: int
    b: int
    a: int = 255

    def to_tuple(self):
        return (self.r, self.g, self.b, self.a)


@dataclass(frozen=True)
class RuleArguments:
    rule_type: str
    channel: str
    show_on_true: bool
    initial_value: bool
    visMin: int
    visMax: int

    def to_tuple(self):
        return (self.rule_type, self.channel, self.show_on_true, self.initial_value, self.visMin, self.visMax)

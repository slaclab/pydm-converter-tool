from dataclasses import dataclass


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
    show_on_true: bool
    initial_value: bool
    visMin: int
    visMax: int

    def __iter__(self):
        yield self.rule_type
        yield self.channel
        yield self.show_on_true
        yield self.initial_value
        yield self.visMin
        yield self.visMax

    def to_tuple(self):
        return (self.rule_type, self.channel, self.show_on_true, self.initial_value, self.visMin, self.visMax)

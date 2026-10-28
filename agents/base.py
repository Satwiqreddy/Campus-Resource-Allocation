"""Message passing shared by all agents (FIPA-ACL style performatives)."""
from dataclasses import dataclass, field

import mesa


@dataclass
class Message:
    sender: str
    receiver: str
    performative: str   # REQUEST, QUERY, PROPOSE, ACCEPT, REJECT, COMMIT, ...
    content: dict = field(default_factory=dict)
    text: str = ""      # human-readable summary for the demo log


class CampusAgent(mesa.Agent):
    """An agent owns private state and only talks to others through messages."""

    def __init__(self, model, name):
        super().__init__(model)
        self.name = name
        model.registry[name] = self

    def send(self, receiver, performative, text="", **content):
        return self.model.deliver(Message(self.name, receiver, performative, content, text))

    def reply(self, msg, performative, text="", **content):
        return Message(self.name, msg.sender, performative, content, text)

    def receive(self, msg):
        handler = getattr(self, "on_" + msg.performative.lower(), None)
        if handler is None:
            return self.reply(msg, "NOT_UNDERSTOOD", f"cannot handle {msg.performative}")
        return handler(msg)

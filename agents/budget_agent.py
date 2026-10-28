"""Budget Agent: owns the fest ledger, approves or rejects spending."""
from agents.base import CampusAgent


class BudgetAgent(CampusAgent):
    def __init__(self, model, total, committed=0):
        super().__init__(model, "BudgetAgent")
        self.total = total
        self.ledger = {"(already committed)": committed} if committed else {}

    @property
    def remaining(self):
        return self.total - sum(self.ledger.values())

    def on_quote(self, msg):
        costs = msg.content["costs"]
        approved = [c <= self.remaining for c in costs]
        if approved[0]:
            return self.reply(msg, "APPROVE", f"₹{costs[0]:,} fits (₹{self.remaining:,} left)", approved=approved)
        return self.reply(msg, "REJECT",
                          f"₹{costs[0]:,} exceeds remaining ₹{self.remaining:,}; "
                          f"{sum(approved)} cheaper alternative(s) fit", approved=approved)

    def on_balance(self, msg):
        return self.reply(msg, "BALANCE", f"₹{self.remaining:,} of ₹{self.total:,} left", remaining=self.remaining)

    def on_commit(self, msg):
        cost, event = msg.content["cost"], msg.content["event"]
        if cost > self.remaining:
            return self.reply(msg, "REFUSE", f"₹{cost:,} exceeds remaining ₹{self.remaining:,}")
        self.ledger[event] = cost
        return self.reply(msg, "COMMITTED", f"{event}: ₹{cost:,} (₹{self.remaining:,} left)")

    def on_release(self, msg):
        self.ledger.pop(msg.content["event"], None)

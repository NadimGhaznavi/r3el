from ax3l.interface.LLMHealth import LLMHealth
from ax3l.interface.Systemd import Systemd


class CheckServices:
    def run(self, unit: str, health_url: str) -> dict:
        return {
            "ax3l_unit": unit,
            "ax3l_state": Systemd().state(unit),
            "llm": LLMHealth().status(health_url),
        }

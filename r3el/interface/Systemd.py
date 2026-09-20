import subprocess


class Systemd:
    def state(self, unit: str) -> str:
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=ActiveState", "--value"],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()

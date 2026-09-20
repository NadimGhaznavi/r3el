"""Dev/QA health stub. Does not provide inference or execute tools."""

from ax3l.interface.HealthServer import HealthServer


if __name__ == "__main__":
    HealthServer().run("llm-server", mode="health-only-stub")

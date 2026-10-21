"""Listener bindings and local client destinations from resolved settings."""

from r3el.interface.Configuration import Configuration


class Network:
    @staticmethod
    def binding(use: str) -> tuple[str, int]:
        listener = Configuration.load()['network'][use]
        return listener['interface'], listener['port']

    @classmethod
    def destination(cls, use: str) -> tuple[str, int]:
        interface, port = cls.binding(use)
        return ('127.0.0.1' if interface == '0.0.0.0' else interface), port

    @classmethod
    def endpoint(cls, use: str, *, destination: bool = False) -> str:
        interface, port = cls.destination(use) if destination else cls.binding(use)
        return f'tcp://{interface}:{port}'

"""Resolve production listener configuration at the application boundary."""

from functools import cache
from ipaddress import IPv4Address
import json
from pathlib import Path

from r3el.constants.DR3el import DR3el


class Configuration:
    @staticmethod
    def path() -> Path:
        return Path(DR3el.BASE_DIR) / 'conf' / 'r3el.json'

    @staticmethod
    def defaults() -> dict:
        return {'network': {use: {'interface': interface, 'port': port}
                            for use, interface, port in DR3el.CMDB_NETWORK}}

    @classmethod
    def resolve(cls, path: Path) -> dict:
        settings = cls.defaults()
        try:
            contents = path.read_text()
        except FileNotFoundError:
            return settings
        try:
            overrides = json.loads(contents)
        except json.JSONDecodeError as error:
            raise ValueError(f'{path}: {error}') from error
        if not isinstance(overrides, dict) or overrides.keys() - {'network'}:
            raise ValueError(f'{path}: expected an object with only network settings')
        network = overrides.get('network', {})
        if not isinstance(network, dict):
            raise ValueError(f'{path}: network must be an object')
        for use, values in network.items():
            field = f'{path}: network.{use}'
            if use not in settings['network']:
                raise ValueError(f'{field}: unknown listener use')
            if not isinstance(values, dict) or values.keys() - {'interface', 'port'}:
                raise ValueError(f'{field}: expected only interface and port fields')
            if 'interface' in values:
                address = values['interface']
                try:
                    if not isinstance(address, str):
                        raise ValueError('expected an IPv4 string')
                    IPv4Address(address)
                except ValueError as error:
                    raise ValueError(f'{field}.interface: invalid IPv4 address') from error
            if 'port' in values:
                port = values['port']
                if type(port) is not int or not 1 <= port <= 65535:
                    raise ValueError(f'{field}.port: expected an integer from 1 to 65535')
            settings['network'][use].update(values)
        return settings

    @classmethod
    @cache
    def load(cls) -> dict:
        return cls.resolve(cls.path())

    @classmethod
    def prepare(cls) -> None:
        """Validate before service changes and create defaults only when missing."""
        path = cls.path()
        cls.resolve(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('x') as stream:
                stream.write(json.dumps(cls.defaults(), indent=2) + '\n')
        except FileExistsError:
            cls.resolve(path)

    @staticmethod
    def database(label: str) -> str:
        return dict(DR3el.CMDB_DATABASES)[label]


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        Configuration.prepare()
    else:
        Configuration.load()

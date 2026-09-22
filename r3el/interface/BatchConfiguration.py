"""Resolve external batch parameters before passing them to activities."""

from pathlib import Path

from r3el.constants.DR3el import DR3el
from r3el.entity.BatchRequest import BatchRequest


class BatchConfiguration:
    @staticmethod
    def resolve(payload: dict) -> BatchRequest:
        if set(payload) != {'input_directory', 'output_directory', 'batch_size'}:
            raise ValueError('Supply input_directory, output_directory, and batch_size.')
        for name in ('input_directory', 'output_directory'):
            value = payload[name]
            if (not isinstance(value, str) or not value.strip() or '\x00' in value
                    or not Path(value).is_absolute()):
                raise ValueError(f'{name} must be an absolute directory path.')
        size = payload['batch_size']
        if type(size) is not int or size not in DR3el.BATCH_SIZES:
            raise ValueError(f'batch_size must be one of {DR3el.BATCH_SIZES}.')
        return BatchRequest(**payload)

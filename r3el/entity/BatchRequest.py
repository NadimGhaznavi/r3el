"""Validated parameters for a control-requested batch."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchRequest:
    input_directory: str
    output_directory: str
    batch_size: int

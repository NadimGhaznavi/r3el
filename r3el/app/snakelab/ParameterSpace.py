"""Identify finite schema domains and their legal combinations."""

from fractions import Fraction
from itertools import product
from math import ceil, floor

from ax3l.app.snakelab.SingleParameters import SCHEMA, SINGLE_PARAMETERS
from ax3l.app.snakelab.PairParameters import PAIR_PARAMETERS


def finite_values(field):
    """Return exact numeric choices, or None for a continuous/unbounded domain."""
    if 'const' in field:
        return (Fraction(str(field['const'])),)
    if 'enum' in field:
        return tuple(Fraction(str(value)) for value in field['enum'])
    lower = field.get('exclusiveMinimum', field.get('minimum'))
    upper = field.get('exclusiveMaximum', field.get('maximum'))
    if lower is None or upper is None:
        return None
    if field['type'] == 'integer':
        # Integer multiples of a rational p/q are multiples of p.
        step = Fraction(str(field.get('multipleOf', 1))).numerator
    elif 'multipleOf' in field:
        step = Fraction(str(field['multipleOf']))
    else:
        return None
    lower, upper = Fraction(str(lower)) / step, Fraction(str(upper)) / step
    first = floor(lower) + 1 if 'exclusiveMinimum' in field else ceil(lower)
    last = ceil(upper) - 1 if 'exclusiveMaximum' in field else floor(upper)
    return tuple(step * index for index in range(first, last + 1))


def parameter_paths(parameter):
    if parameter in SINGLE_PARAMETERS:
        return (SINGLE_PARAMETERS[parameter][0],)
    return PAIR_PARAMETERS[parameter]


def finite_choices(parameter):
    domains = []
    for path in parameter_paths(parameter):
        field = SCHEMA
        for key in path:
            field = field['properties'][key]
        values = finite_values(field)
        if values is None:
            return None
        domains.append(values)
    return set(product(*domains))

"""Read Snake Lab simulation data through AX3L's database manager."""

from ax3l.app.snakelab.SingleParameters import SCHEMA, SINGLE_PARAMETERS
from ax3l.app.DbMgr import DbMgr
from ax3l.app.snakelab.ParameterSpace import finite_choices, parameter_paths
from fractions import Fraction


def _configuration_fields(node, path=()):
    for name, field in node["properties"].items():
        parts = path + (name,)
        if field["type"] == "object":
            yield from _configuration_fields(field, parts)
        else:
            yield "_".join(parts), parts, field["type"]


CONFIGURATION_FIELDS = tuple(_configuration_fields(SCHEMA))
CONFIGURATION_COLUMNS = ", ".join(column for column, _, _ in CONFIGURATION_FIELDS)


def _config_from_row(row):
    config = {}
    for column, path, kind in CONFIGURATION_FIELDS:
        target = config
        for part in path[:-1]:
            target = target.setdefault(part, {})
        target[path[-1]] = int(row[column]) if kind == "integer" else float(row[column])
    return config


def _config_values(config):
    values = []
    for _, path, _ in CONFIGURATION_FIELDS:
        value = config
        for part in path:
            value = value[part]
        values.append(value)
    return tuple(values)


def _comparable(excluded):
    return " AND ".join(
        f"c.{column} = g.{column}"
        for column, _, _ in CONFIGURATION_FIELDS if column not in excluded
    )


class SnakeLabDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def parameter_space_exhausted(self, golden_run_id: str, parameter: str) -> bool:
        choices = finite_choices(parameter)
        if choices is None:
            return False
        columns = ["_".join(path) for path in parameter_paths(parameter)]
        conditions = _comparable(set(columns))
        rows = self._db.query(f"""
            SELECT DISTINCT {', '.join('c.' + column for column in columns)}
            FROM simulation_runs r JOIN configurations c ON c.run_id = r.run_id
            JOIN configurations g ON g.run_id = %s
            WHERE {conditions}
        """, (golden_run_id,))
        # Duplicate protection rejects existing configurations in every status.
        tried = {tuple(Fraction(str(row[column])) for column in columns) for row in rows}
        return choices <= tried

    def get_num_sims(self) -> int:
        """Count all stored runs, including repeated configurations and all statuses."""
        return self._db.query("SELECT COUNT(*) AS num_sims FROM simulation_runs")[0]["num_sims"]

    def get_high_score(self) -> int | None:
        """Return the highest recorded score across all runs, or None before any score."""
        return self._db.query(
            "SELECT MAX(high_score) AS high_score FROM simulation_runs"
        )[0]["high_score"]

    def get_run_scores(self) -> list[int | None]:
        """Return every run's score in submission order, including unscored runs."""
        return [row["high_score"] for row in self._db.query(
            "SELECT high_score FROM simulation_runs ORDER BY id"
        )]

    def get_config(self, run_id: str) -> dict | None:
        rows = self._db.query(
            f"SELECT {CONFIGURATION_COLUMNS} FROM configurations WHERE run_id = %s", (run_id,)
        )
        return _config_from_row(rows[0]) if rows else None

    def is_config_unique(self, config: dict) -> bool:
        """Compare all configuration values across every run and status."""
        return self.find_config_run(config) is None

    def get_run_summary(self, run_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT run_id, project_version, high_score, completed_at, high_score_snapshot "
            "FROM simulation_runs WHERE run_id = %s", (run_id,),
        )
        return rows[0] if rows else None

    def get_run_result(self, run_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT r.run_id, r.status, r.high_score, c.* FROM simulation_runs r "
            "JOIN configurations c ON c.run_id = r.run_id WHERE r.run_id = %s",
            (run_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {**{key: row[key] for key in ("run_id", "status", "high_score")},
                "config": _config_from_row(row)}

    def get_learning_rate_history(self) -> list[dict]:
        return self._db.query("""
            SELECT r.run_id, r.status, r.high_score,
                   c.training_learning_rate AS learning_rate
            FROM simulation_runs r JOIN configurations c ON c.run_id = r.run_id
            ORDER BY c.training_learning_rate, r.id
        """)

    def get_episode_losses(self, run_id: str) -> list[tuple[int, float | None]]:
        """Read losses in episode order, preserving episodes with no training loss."""
        rows = self._db.query(
            "SELECT episode, loss FROM simulation_episodes WHERE run_id = %s ORDER BY episode",
            (run_id,),
        )
        return [(row["episode"], row["loss"]) for row in rows]

    def find_config_run(self, config: dict) -> str | None:
        conditions = " AND ".join(f"c.{column} = %s" for column, _, _ in CONFIGURATION_FIELDS)
        rows = self._db.query(
            "SELECT r.run_id FROM simulation_runs r JOIN configurations c ON c.run_id = r.run_id "
            f"WHERE {conditions} ORDER BY r.id DESC LIMIT 1", _config_values(config)
        )
        return rows[0]["run_id"] if rows else None

    def get_learning_rate_report(self, golden_run_id: str) -> list[dict]:
        return self.get_parameter_report(golden_run_id, "learning_rate")

    def get_epsilon_report(self, golden_run_id: str) -> list[dict]:
        """Group comparable epsilon pairs, including gaps in observed values."""
        conditions = _comparable({"seed", "epsilon_initial", "epsilon_decay"})
        rows = self._db.query(f"""
            SELECT r.status, r.high_score,
                   c.epsilon_initial AS initial, c.epsilon_decay AS decay
            FROM simulation_runs r JOIN configurations c ON c.run_id = r.run_id
            JOIN configurations g ON g.run_id = %s
            WHERE {conditions}
            ORDER BY c.epsilon_initial, c.epsilon_decay, r.id
        """, (golden_run_id,))
        grouped = {}
        decays = set()
        for row in rows:
            initial = row["initial"]
            decay = row["decay"]
            decays.add(decay)
            scores = grouped.setdefault(initial, {}).setdefault(decay, [])
            if row["status"] == "completed" and row["high_score"] is not None:
                scores.append(row["high_score"])
        return [
            {"initial": initial, "pairs": [
                {"decay": decay, "scores": sorted(grouped[initial].get(decay, []))}
                for decay in sorted(decays)
            ]}
            for initial in sorted(grouped)
        ]

    def get_reward_report(self, golden_run_id: str) -> dict:
        """Return the full legal distance-reward grid across comparable seeds."""
        fields = SCHEMA["properties"]["game"]["properties"]["rewards"]["properties"]
        closer = fields["closer_to_food"]
        further = fields["further_from_food"]
        grid = {
            str(first): {str(second): []
                         for second in range(further["minimum"], further["maximum"] + 1)}
            for first in range(closer["minimum"], closer["maximum"] + 1)
        }
        conditions = _comparable({"seed", "game_rewards_closer_to_food", "game_rewards_further_from_food"})
        rows = self._db.query(f"""
            SELECT r.status, r.high_score,
                   c.game_rewards_closer_to_food AS closer_to_food,
                   c.game_rewards_further_from_food AS further_from_food
            FROM simulation_runs r JOIN configurations c ON c.run_id = r.run_id
            JOIN configurations g ON g.run_id = %s
            WHERE {conditions}
            ORDER BY r.id
        """, (golden_run_id,))
        for row in rows:
            first = row["closer_to_food"]
            second = row["further_from_food"]
            # Historical configurations outside today's legal grid have no cell.
            if first not in range(closer["minimum"], closer["maximum"] + 1) or second not in range(further["minimum"], further["maximum"] + 1):
                continue
            if row["status"] == "completed" and row["high_score"] is not None:
                grid[str(int(first))][str(int(second))].append(row["high_score"])
        for pairs in grid.values():
            for scores in pairs.values():
                scores.sort()
        return grid

    def get_parameter_report(self, golden_run_id: str, parameter: str) -> list[dict]:
        path, _ = SINGLE_PARAMETERS[parameter]
        column = "_".join(path)
        conditions = _comparable({"seed", column})
        rows = self._db.query(f"""
            SELECT r.run_id, r.status, r.high_score,
                   c.{column} AS {parameter}, c.seed = g.seed AS current_seed
            FROM simulation_runs r JOIN configurations c ON c.run_id = r.run_id
            JOIN configurations g ON g.run_id = %s
            WHERE {conditions}
            ORDER BY c.{column}, r.id
        """, (golden_run_id,))
        grouped = {}
        for row in rows:
            value = row[parameter]
            entry = grouped.setdefault(value, {parameter: value, "results": [], "history": []})
            if row["current_seed"]:
                entry["results"].append({key: row[key] for key in ("run_id", "status", "high_score")})
            elif row["status"] == "completed" and row["high_score"] is not None:
                entry["history"].append(row["high_score"])
        for entry in grouped.values():
            entry["history"].sort()
        return list(grouped.values())

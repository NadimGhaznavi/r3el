"""Query Snake Lab through its control interface and MariaDB database."""

from uuid import UUID, uuid4

import zmq

from ax3l.constants.DSnakeLab import DSnakeLab
from ax3l.app.DbMgr import DbMgr
from ax3l.app.snakelab.SnakeLabDb import SnakeLabDb


class SnakeLabQueryError(RuntimeError):
    def __init__(self, error):
        super().__init__(f"Snake Lab query failed: {error}")
        self.code = error.get("code") if isinstance(error, dict) else None


class SimulationUnavailable(RuntimeError):
    """A run has left the server without a durable terminal result."""


class SnakeLab:
    def __init__(self, endpoint: str = DSnakeLab.ENDPOINT):
        self.endpoint = endpoint

    def get_num_sims(self) -> int:
        """Return the total stored run count using Ax3l’s DB credentials.

        Database errors propagate. The connection is closed after each query,
        and no tables are initialized in the Snake Lab database.
        """
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_num_sims()
        finally:
            db.close()

    def get_high_score(self) -> int | None:
        """Return the experiment's highest recorded score across configs and seeds."""
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_high_score()
        finally:
            db.close()

    def get_run_scores(self) -> list[int | None]:
        """Return all recorded run scores, oldest submissions first."""
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_run_scores()
        finally:
            db.close()

    def is_simulation_running(self) -> bool:
        """Return whether work is running, paused, cancelling, or queued.

        This synchronous call does not retry. Transport and protocol errors
        propagate; an unavailable server is not an idle server.
        """
        payload = self._request("simulation.active", {})
        if "run" not in payload:
            raise ValueError("Snake Lab response payload must contain run")
        run = payload["run"]
        if run is None:
            return False
        if not isinstance(run, dict) or run.get("state") not in (
            "running", "paused", "cancelling", "queued"
        ):
            raise ValueError("Snake Lab response has an invalid active run state")
        return True

    def get_config(self, run_id: str) -> dict | None:
        UUID(run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_config(run_id)
        finally:
            db.close()

    def get_run_summary(self, run_id: str) -> dict | None:
        UUID(run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_run_summary(run_id)
        finally:
            db.close()

    def get_run_result(self, run_id: str) -> dict | None:
        UUID(run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_run_result(run_id)
        finally:
            db.close()

    def get_learning_rate_history(self) -> list[dict]:
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_learning_rate_history()
        finally:
            db.close()

    def find_config_run(self, config: dict) -> str | None:
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).find_config_run(config)
        finally:
            db.close()

    def get_parameter_report(self, golden_run_id: str, parameter: str) -> list[dict]:
        UUID(golden_run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_parameter_report(golden_run_id, parameter)
        finally:
            db.close()

    def parameter_space_exhausted(self, golden_run_id: str, parameter: str) -> bool:
        UUID(golden_run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).parameter_space_exhausted(golden_run_id, parameter)
        finally:
            db.close()

    def get_epsilon_report(self, golden_run_id: str) -> list[dict]:
        UUID(golden_run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_epsilon_report(golden_run_id)
        finally:
            db.close()

    def get_reward_report(self, golden_run_id: str) -> dict:
        UUID(golden_run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_reward_report(golden_run_id)
        finally:
            db.close()

    def get_learning_rate_report(self, golden_run_id: str) -> list[dict]:
        UUID(golden_run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_learning_rate_report(golden_run_id)
        finally:
            db.close()

    def is_config_unique(self, config: dict) -> bool:
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).is_config_unique(config)
        finally:
            db.close()

    def get_episode_losses(self, run_id: str) -> list[tuple[int, float | None]]:
        UUID(run_id)
        db = DbMgr(database=DSnakeLab.DATABASE, initialize_event_tables=False)
        try:
            return SnakeLabDb(db).get_episode_losses(run_id)
        finally:
            db.close()

    def submit_simulation(self, config: dict) -> str:
        """Submit once and return the queued run ID; never retry a submission."""
        payload = self._request("simulation.submit", {"config": config})
        if payload.get("state") != "queued" or not isinstance(payload.get("run_id"), str):
            raise ValueError("Snake Lab response has an invalid submission")
        UUID(payload["run_id"])
        return payload["run_id"]

    def get_simulation_status(self, run_id: str) -> str:
        UUID(run_id)
        try:
            payload = self._request("simulation.status", {"run_id": run_id})
        except SnakeLabQueryError as error:
            if error.code != "run_not_found":
                raise
            # The control server only remembers runs from its current process.
            result = self.get_run_result(run_id)
            if result is not None and result["status"] in ("completed", "failed", "cancelled"):
                return result["status"]
            raise SimulationUnavailable(
                f"Simulation {run_id} is unknown to the current Snake Lab server "
                "and has no stored terminal result."
            ) from error
        if payload.get("run_id") != run_id or payload.get("state") not in (
            "queued", "running", "paused", "cancelling", "completed", "failed", "cancelled"
        ):
            raise ValueError("Snake Lab response has an invalid run status")
        return payload["state"]

    def _request(self, method: str, payload: dict) -> dict:
        request_id = str(uuid4())
        request = {
            "protocol_version": DSnakeLab.PROTOCOL_VERSION,
            "request_id": request_id,
            "method": method,
            "payload": payload,
        }
        with zmq.Context() as context:
            with context.socket(zmq.REQ) as socket:
                socket.setsockopt(zmq.LINGER, 0)
                socket.setsockopt(zmq.SNDTIMEO, DSnakeLab.TIMEOUT_MS)
                socket.setsockopt(zmq.RCVTIMEO, DSnakeLab.TIMEOUT_MS)
                socket.connect(self.endpoint)
                socket.send_json(request)
                response = socket.recv_json()

        if not isinstance(response, dict):
            raise ValueError("Snake Lab response must be an object")
        version = response.get("protocol_version")
        if type(version) is not int or version != DSnakeLab.PROTOCOL_VERSION:
            raise ValueError("Snake Lab response has an unsupported protocol version")
        if response.get("request_id") != request_id:
            raise ValueError("Snake Lab response request_id does not match")
        if response.get("status") == "error":
            raise SnakeLabQueryError(response.get("error"))
        if response.get("status") != "ok":
            raise ValueError("Snake Lab response has an invalid status")
        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Snake Lab response payload must be an object")
        return payload

import argparse
import os
from importlib import import_module
from threading import Thread

from ax3l.interface.HealthServer import HealthServer
from ax3l.constants.DAx3l import DAx3l
from ax3l.server.ToolHandler import handle_tool
from ax3l.zmq.ZMQServer import ZMQServer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ax3l and its single-parameter optimization loop.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--llm-url", help="Use this LLM server for optimization")
    parser.add_argument("--output", default="tmp/snakelab")
    parser.add_argument("--zmq-endpoint", default=os.environ.get("AX3L_ZMQ_ENDPOINT", DAx3l.ZMQ_ENDPOINT))
    args = parser.parse_args()
    mode = "optimization" if args.llm_url else "skeleton"
    with ZMQServer(args.zmq_endpoint, handle_tool) as tool_server, HealthServer().make_server("ax3l-server", args.port, mode) as server:
        if not args.llm_url:
            server.serve_forever()
            return 0
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            loop = import_module("ax3l.app.snakelab.main-loop")
            return loop.main(["--url", args.llm_url, "--output", args.output, "--zmq-endpoint", tool_server.endpoint])
        finally:
            server.shutdown()
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main())

"""Dispatch domain tool requests on the Ax3l side of the transport boundary."""

import json

from ax3l.app.DbMgr import DbMgr
from ax3l.constants.DEventCategory import DEventCategory
from ax3l.app.snakelab.SubmitSingleValueHandler import SubmitSingleValueHandler
from ax3l.app.snakelab.SubmitPairValuesHandler import SubmitPairValuesHandler
from ax3l.zmq.ZMQMsg import ZMQMsg


def handle_tool(request: ZMQMsg) -> dict:
    db = DbMgr()
    try:
        category = DEventCategory.Tool
        db.log(category.RECEIVED, category.CATEGORY, "INFO",
               json.dumps(request.to_dict(), ensure_ascii=False))
        handlers = {"submit_single_value": SubmitSingleValueHandler,
                    "submit_pair_values": SubmitPairValuesHandler}
        if request.target != "snakelab" or request.method not in handlers:
            return {"status": "error", "error": {"code": "unknown_method", "message": "Unknown domain or method"}}
        return handlers[request.method](db).submit(request.payload)
    finally:
        db.close()

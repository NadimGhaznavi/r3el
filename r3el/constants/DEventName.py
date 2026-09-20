"""Stable names for individual events within the category hierarchy."""


from r3el.constants.DEventCategory import DEventCategory as Categories


class DEventName:
    SERVER_STARTED = "started"
    SERVER_STOPPED = "stopped"
    BATCH_STARTED = "batch_started"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"
    BATCH_CANCELLED = "batch_cancelled"
    FILES_RETRIEVED = "files_retrieved"
    ITEM_STARTED = "item_started"
    ITEM_COMPLETED = "item_completed"
    ATTEMPT_STARTED = "attempt_started"
    ATTEMPT_FAILED = "attempt_failed"
    ATTEMPT_CANCELLED = "attempt_cancelled"
    PROMPT_SENT = "prompt_sent"
    REPLY_RECEIVED = "reply_received"
    TOOL_STARTED = "tool_started"
    TOOL_RECEIVED = "tool_received"
    TOOL_COMPLETED = "tool_completed"
    SUBMISSION_REJECTED = "submission_rejected"
    SUBMISSION_ACCEPTED = "submission_accepted"

    # Every event bucket has exactly one category/subcategory parent.
    CHILDREN = {
        Categories.Server.LIFECYCLE: (SERVER_STARTED, SERVER_STOPPED),
        Categories.Batch.LIFECYCLE: (BATCH_STARTED, BATCH_COMPLETED, BATCH_FAILED, BATCH_CANCELLED),
        Categories.Batch.DISCOVERY: (FILES_RETRIEVED,),
        Categories.Identification.CONVERSATION: (
            ITEM_STARTED, ATTEMPT_STARTED, ATTEMPT_FAILED, ATTEMPT_CANCELLED,
            PROMPT_SENT, REPLY_RECEIVED),
        Categories.Identification.TOOL: (TOOL_STARTED, TOOL_RECEIVED, TOOL_COMPLETED),
        Categories.Identification.VALIDATION: (SUBMISSION_REJECTED, SUBMISSION_ACCEPTED),
        Categories.Identification.RESULT: (ITEM_COMPLETED,),
    }
    PARENTS = {name: parent for parent, names in CHILDREN.items() for name in names}
    ALL = tuple(PARENTS)

"""The shared category hierarchy for event writers and report filters."""

from r3el.entity.EventCategory import EventCategory


class DEventCategory:
    class Server:
        NAME = "Server"
        LIFECYCLE = EventCategory(NAME, "Lifecycle")

    class Batch:
        NAME = "Batch"
        LIFECYCLE = EventCategory(NAME, "Lifecycle")
        DISCOVERY = EventCategory(NAME, "Discovery")
        BATCH_IDENTIFICATION = EventCategory(NAME, "BatchIdentification")

    class Identification:
        NAME = "Identification"
        CONVERSATION = EventCategory(NAME, "Conversation")
        VALIDATION = EventCategory(NAME, "Validation")

    class Prompt:
        NAME = "Prompt"
        TOOL_CONVERSATION = EventCategory(NAME, "ToolConversation")
        SUBMISSION_HANDLER = EventCategory(NAME, "SubmissionHandler")
        LLM_PROMPT = EventCategory(NAME, "LLMPrompt")

    ALL = (Server.LIFECYCLE, Batch.LIFECYCLE, Batch.DISCOVERY, Batch.BATCH_IDENTIFICATION,
           Identification.CONVERSATION,
           Identification.VALIDATION, Prompt.TOOL_CONVERSATION, Prompt.SUBMISSION_HANDLER, Prompt.LLM_PROMPT)
    CHILDREN = {}
    for classification in ALL:
        CHILDREN.setdefault(classification.category, []).append(classification.subcategory)
    CHILDREN = {parent: tuple(children) for parent, children in CHILDREN.items()}
    del classification

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

    class Prompt:
        NAME = "Prompt"
        TOOL_CONVERSATION = EventCategory(NAME, "ToolConversation")
        SUBMISSION_HANDLER = EventCategory(NAME, "SubmissionHandler")
        LLM_PROMPT = EventCategory(NAME, "LLMPrompt")

    class TMDB:
        NAME = "TMDB"
        SEARCH = EventCategory(NAME, "Search")
        RESULT = EventCategory(NAME, "Result")

    ALL = (Server.LIFECYCLE, Batch.LIFECYCLE, Batch.DISCOVERY, Batch.BATCH_IDENTIFICATION,
           Prompt.TOOL_CONVERSATION, Prompt.SUBMISSION_HANDLER, Prompt.LLM_PROMPT,
           TMDB.SEARCH, TMDB.RESULT)
    CHILDREN = {}
    for classification in ALL:
        CHILDREN.setdefault(classification.category, []).append(classification.subcategory)
    CHILDREN = {parent: tuple(children) for parent, children in CHILDREN.items()}
    del classification

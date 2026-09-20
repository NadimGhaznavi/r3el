"""Run one conversation until MCP accepts a simulation submission."""

import asyncio
import json

from uuid import uuid4

from ax3l.constants.DAx3l import DAx3l
from ax3l.constants.DEventCategory import DEventCategory as Events


async def converse(llm, output, db, tools, prompts, *, parameter: str | None = None) -> str:
    process_id = str(uuid4())
    print(f"Conversation: {process_id}", flush=True)
    conversation_id = db.log(Events.Conversation.STARTED, Events.Conversation.CATEGORY,
                             "INFO", f"Conversation started with {llm.url}.", process_id=process_id)

    def log(category, name, content, level="INFO", *, source_name=None):
        return db.log(name, category.CATEGORY, level, content, process_id=process_id,
                      parent_event_id=conversation_id, source_name=source_name,
                      parameter=parameter if category is Events.Conversation and name == Events.Conversation.PROMPT else None)

    outcome, level = "Simulation submitted.", "INFO"
    try:
        tool_name = tools.definition["function"]["name"]
        argument_names = set(tools.definition["function"]["parameters"]["properties"])
        messages = [json.loads(prompt.to_json()) for prompt in prompts]
        for prompt, message in zip(prompts, messages):
            log(Events.Conversation, Events.Conversation.PROMPT, json.dumps(message, ensure_ascii=False),
                source_name=prompt.source_name)
        turn = 0
        while True:
            turn += 1
            payload = json.dumps({"messages": messages, "tools": [tools.definition],
                                  "tool_choice": "required", "parallel_tool_calls": False,
                                  "stream": False}, ensure_ascii=False).encode()
            prefix = output / f"{process_id}-{turn:04d}"
            if DAx3l.RAW_LOGS_ENABLED:
                prefix.with_suffix(".request.json").write_bytes(payload)
            try:
                status, headers, body = await asyncio.to_thread(llm.complete, payload)
                if DAx3l.RAW_LOGS_ENABLED:
                    prefix.with_suffix(".response.body").write_bytes(body)
                    prefix.with_suffix(".response.headers").write_text(f"HTTP status: {status}\n{headers}")
                if status >= 400:
                    raise RuntimeError(f"HTTP {status}: {body.decode(errors='replace')}")
            except Exception as error:
                log(Events.LLM, Events.LLM.REQUEST_FAILED, str(error), "ERROR")
                raise
            reply_id = log(Events.Conversation, Events.Conversation.RESPONSE, body.decode(errors="backslashreplace"))
            choice = json.loads(body)["choices"][0]
            reply = choice["message"]
            calls = reply.get("tool_calls", [])
            if len(calls) != 1 or calls[0]["function"]["name"] != tool_name:
                names = [call["function"]["name"] for call in calls]
                raise ValueError(
                    f"Expected exactly one {tool_name} tool call; received {names!r}, "
                    f"finish_reason={choice.get('finish_reason')!r}. See reply event {reply_id}."
                )
            call = calls[0]
            arguments = json.loads(call["function"]["arguments"])
            messages.append(reply)
            log(Events.Tool, Events.Tool.STARTED, json.dumps(call))
            try:
                if not isinstance(arguments, dict) or set(arguments) != argument_names:
                    result = {"status": "rejected", "code": "invalid_arguments",
                              "source_name": "ToolConversation",
                              "prompt": {"role": "user", "content":
                                  f"Call {tool_name} with exactly these numeric fields: "
                                  + ", ".join(sorted(argument_names)) + "."}}
                else:
                    result = await tools.submit(arguments)
                if result["status"] not in ("ok", "rejected"):
                    raise RuntimeError(f"Tool submission failed: {result}")
            except Exception as error:
                log(Events.Tool, Events.Tool.FAILED, str(error), "ERROR")
                raise
            log(Events.Tool, Events.Tool.COMPLETED, json.dumps(result))
            if result["status"] == "ok":
                return result["run_id"]
            # Explicit validation rejections are safe to correct. Transport failures are not retried.
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})
            feedback = result["prompt"]
            messages.append(feedback)
            log(Events.Conversation, Events.Conversation.PROMPT, json.dumps(feedback, ensure_ascii=False),
                source_name=result.get("source_name", "ToolConversation"))
    except (KeyboardInterrupt, asyncio.CancelledError):
        outcome = "Stopped by user."
        raise
    except BaseException as error:
        outcome, level = f"Conversation stopped: {type(error).__name__}: {error}", "ERROR"
        raise
    finally:
        log(Events.Conversation, Events.Conversation.ENDED, outcome, level)

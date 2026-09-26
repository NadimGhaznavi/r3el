"""Render event reports with the control server's Jinja2 templates."""

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, select_autoescape

from r3el.constants.DR3el import DR3el
from r3el.constants.DMessage import DMessage
from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName
from r3el.entity.MediaFile import MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatchState
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.activity.BatchPreparation import BatchPreparation
from r3el.server.ReplyReasoning import ReplyReasoning
from r3el.server.MatchResults import MatchResults


class EventPages:
    def __init__(self) -> None:
        self._reasoning = ReplyReasoning()
        self._templates = Environment(
            loader=FileSystemLoader(Path(__file__).with_name('templates')),
            autoescape=select_autoescape(['html']), undefined=StrictUndefined,
        )
        self._templates.filters['reasoning_preview'] = self.reasoning_preview
        self._templates.filters['prompt_preview'] = self.prompt_preview
        self._templates.filters['from_json'] = json.loads
        self._templates.filters['utc_iso'] = lambda value: value.replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds')
        self._templates.globals['settings'] = DR3el
        self._templates.globals['messages'] = DMessage
        self._templates.globals['event_types'] = DEventName
        self._templates.globals['file_states'] = MediaFileState
        self._templates.globals['file_actions'] = MediaFileAction
        self._templates.globals['categories'] = DEventCategory.CHILDREN
        self._templates.globals['event_parents'] = {
            name: {'category': parent.category, 'subcategory': parent.subcategory}
            for name, parent in sorted(DEventName.PARENTS.items())
        }

    @staticmethod
    def message(content: str) -> dict:
        """Decode a stored message and prepare its generic text display."""
        # Lifecycle messages are plain text; conversation messages contain JSON.
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            return {'payload': content, 'text': content}
        return {'payload': value, 'text': json.dumps(value, ensure_ascii=False, indent=2)}

    def message_template(self, name: str) -> Template:
        """Use an event's presentation when available, otherwise the default."""
        return self._templates.select_template([
            f'messages/{name}.html', 'messages/default.html',
        ])

    @staticmethod
    def prompt_preview(content: str) -> str:
        """Show the first 20 characters, extending to finish the current word."""
        end = 20
        while (end < len(content) and not content[end - 1].isspace()
               and not content[end].isspace()):
            end += 1
        return content[:end].rstrip() + ('...' if end < len(content) else '')

    @staticmethod
    def reasoning_preview(content: str) -> str:
        """Extract a short first line from the raw model response logged as data."""
        reasoning = ReplyReasoning.extract(content)
        if reasoning is None:
            return '...'
        return reasoning.split('\n', 1)[0][:20].rstrip('\r') + '...'

    def render(self, template: str, **values) -> bytes:
        if template == 'match.html':
            values['result'] = MatchResults(values['reference']).prepare(values['match'])
            values['response_json'] = json.dumps(values['match'].resolved_response, ensure_ascii=False, indent=2)
        if template == 'control.html':
            values['control_url'] = '/control?refresh=' + str(values['refresh']) if values['refresh'] else '/control'
            values.setdefault('matching_job', None)
            event = values.setdefault('latest_event', None)
            values['latest_event_message'] = (
                self.message_template(event['name']).render(
                    event=event, message=self.message(event['content']))
                if event is not None else '')
            workspace = values['workspace']
            values['automatic_processing'] = workspace is not None and workspace.in_progress
            values['stop_ready'] = (workspace is not None and not workspace.stop_requested
                                    and (values['automatic_processing'] or values['matching_job'] is not None))
            values['process_ready'] = (workspace is not None and BatchPreparation.ready(workspace)
                                       and not workspace.stop_requested and not values['automatic_processing'])
            values['has_match_results'] = workspace is not None and any(
                item.tmdb_match is not None for item in workspace.files)
            values['last_updated'] = datetime.now(timezone.utc)
            values.setdefault('result', None)
            values.setdefault('input_directory', workspace.source_directory if workspace else DR3el.FILM_DIR)
            values.setdefault('output_directory', workspace.destination_directory if workspace else DR3el.MEDIA_DIR)
            values.setdefault('batch_size', workspace.requested_size if workspace else DR3el.BATCH_SIZE)
        if template == 'events.html':
            values['events'] = [
                dict(event, message=self.message(event['content']),
                     message_template=self.message_template(event['name']))
                for event in values['events']
            ]
            category, subcategory = values['category'], values['subcategory']
            values['subcategories'] = sorted({
                parent.subcategory for parent in DEventCategory.ALL
                if category is None or parent.category == category
            })
            values['event_names'] = sorted(
                name for name, parent in DEventName.PARENTS.items()
                if (category is None or parent.category == category)
                and (subcategory is None or parent.subcategory == subcategory)
            )
        elif template == 'event.html':
            values['message'] = self.message(values['event']['content'])
            if values['event']['name'] == DEventName.REPLY_RECEIVED:
                values['reasoning'] = self._reasoning.render(values['message']['payload'])
        return self._templates.get_template(template).render(**values).encode('utf-8')

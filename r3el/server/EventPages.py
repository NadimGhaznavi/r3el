"""Render event reports with the control server's Jinja2 templates."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, select_autoescape

from r3el.constants.DEventCategory import DEventCategory
from r3el.constants.DEventName import DEventName


class EventPages:
    def __init__(self) -> None:
        self._templates = Environment(
            loader=FileSystemLoader(Path(__file__).with_name('templates')),
            autoescape=select_autoescape(['html']), undefined=StrictUndefined,
        )
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

    def render(self, template: str, **values) -> bytes:
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
        return self._templates.get_template(template).render(**values).encode('utf-8')

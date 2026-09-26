"""Recognize two-part movie directories without retaining unmatched items."""

from collections import Counter
from pathlib import Path
from uuid import uuid4

from r3el.activity.EventWriter import EventWriter
from r3el.activity.MovieFormats import MovieFormats
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFile import MediaFile, MediaFileIssue
from r3el.entity.MediaFileBatch import MediaFileBatch
from r3el.interface.DirectoryFiles import DirectoryFiles
from r3el.interface.WorkspaceDb import WorkspaceDb


class DirectoryDiscovery:
    def run(self, batch: MediaFileBatch, workspace: WorkspaceDb, log: EventWriter) -> None:
        if batch.directories_scanned:
            return
        filesystem = DirectoryFiles()
        items, claimed = [], set()
        for directory in filesystem.directories(batch.source_directory, batch.destination_directory):
            workspace.check_stop(batch.id)
            item_id = str(uuid4())
            item_log = EventWriter(log.record, {**log.context, 'item_id': item_id,
                                               'directory': str(directory)}, log.parent_event_id)
            item_log.write(Categories.Batch.DISCOVERY, Names.DIRECTORY_SCAN_STARTED,
                           {'directory': str(directory)}, source='DirectoryDiscovery')
            listing, files = filesystem.scan(directory, batch.destination_directory)
            media = sorted((path for path, size in files
                            if size > 100 * 1024 * 1024
                            and Path(path).suffix.lower().lstrip('.') in MovieFormats.ORDER),
                           key=lambda path: (MovieFormats.rank(path), path))
            matched = len(media) == 2 and not claimed.intersection(media)
            item_log.write(Categories.Batch.DISCOVERY, Names.DIRECTORY_SCAN_COMPLETED,
                           {'directory': str(directory), 'find-ls': listing, 'media_files': media,
                            'matched': matched}, source='DirectoryDiscovery')
            if not matched:
                continue
            claimed.update(media)
            attachments = [MediaAttachment(path) for path in media]
            issues = []
            subtitle_names = Counter(Path(path).stem.casefold() for path, _ in files
                                     if Path(path).suffix.lower() == '.srt')
            for path, _ in sorted(files):
                if Path(path).suffix.lower() != '.srt':
                    continue
                candidates = [video for video in media
                              if Path(path).stem.casefold() == Path(video).stem.casefold()]
                if subtitle_names[Path(path).stem.casefold()] != 1:
                    candidates = []
                attachments.append(MediaAttachment(path, 'subtitle',
                                                   media_path=candidates[0] if len(candidates) == 1 else None))
                if len(candidates) != 1:
                    issues.append(MediaFileIssue('unresolved_srt', f'Cannot associate subtitle: {path}'))
                item_log.write(Categories.Batch.DISCOVERY, Names.SUBTITLE_ASSOCIATION,
                               {'path': path, 'media_path': candidates[0] if len(candidates) == 1 else None,
                                'outcome': 'associated' if len(candidates) == 1 else 'unresolved_srt'},
                               source='DirectoryDiscovery')
            items.append(MediaFile(item_id, str(directory), find_ls=listing, attachments=attachments, issues=issues))
            item_log.write(Categories.Batch.DISCOVERY, Names.TWO_PARTS_DETECTED,
                           {'media_file_a': media[0], 'media_file_b': media[1]}, source='DirectoryDiscovery')
        workspace.check_stop(batch.id)
        workspace.append_directories(batch, items, log.prepare(
            Categories.Batch.DISCOVERY, Names.DIRECTORIES_SCANNED,
            {'two_part_movies': len(items)}, source='DirectoryDiscovery'))

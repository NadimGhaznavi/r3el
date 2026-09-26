"""Recognize two-part and dated-movie directories without retaining unmatched items."""

from collections import Counter
from pathlib import Path
import re
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
        selected = sum(item.source_directory is None for item in batch.files)
        selected += len({item.source_directory for item in batch.files if item.source_directory is not None})
        remaining = max(0, batch.requested_size - selected)
        items = []
        matched_directories = 0
        two_part_count = 0
        dated_count = 0
        directories = (filesystem.directories(batch.source_directory, batch.destination_directory)
                       if remaining else [])
        for directory in directories:
            if matched_directories >= remaining:
                break
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
            years = [self.filename_year(path) for path in media]
            different_years = len(media) == 2 and None not in years and years[0] != years[1]
            two_parts = len(media) == 2 and not different_years
            dated_movies = not two_parts and len(media) >= 2 and None not in years
            matched = two_parts or dated_movies
            pattern = 'two_parts' if two_parts else 'dated_movies' if dated_movies else None
            item_log.write(Categories.Batch.DISCOVERY, Names.DIRECTORY_SCAN_COMPLETED,
                           {'directory': str(directory), 'find-ls': listing, 'media_files': media,
                            'matched': matched, 'pattern': pattern, 'media_years': years,
                            'reason': 'different_years' if different_years else None}, source='DirectoryDiscovery')
            if not matched:
                continue
            matched_directories += 1
            attachments = [MediaAttachment(path) for path in media]
            issues = []
            subtitles = sorted(path for path, _ in files if Path(path).suffix.lower() == '.srt')
            associations = self.subtitle_associations(media, subtitles)
            for path in subtitles:
                candidates = [associations[path]] if associations[path] is not None else []
                attachments.append(MediaAttachment(path, 'subtitle',
                                                   media_path=candidates[0] if len(candidates) == 1 else None))
                if len(candidates) != 1:
                    issues.append(MediaFileIssue('unresolved_srt', f'Cannot associate subtitle: {path}'))
                item_log.write(Categories.Batch.DISCOVERY, Names.SUBTITLE_ASSOCIATION,
                               {'path': path, 'media_path': candidates[0] if len(candidates) == 1 else None,
                                'outcome': 'associated' if len(candidates) == 1 else 'unresolved_srt'},
                               source='DirectoryDiscovery')
            if dated_movies:
                dated_count += 1
                for video in media:
                    associated = [attachment for attachment in attachments
                                  if attachment.path == video or attachment.media_path == video]
                    items.append(MediaFile(str(uuid4()), video, source_directory=str(directory),
                                           attachments=associated, issues=list(issues)))
                item_log.write(Categories.Batch.DISCOVERY, Names.DATED_MOVIES_DETECTED,
                               {'media_files': media, 'years': years}, source='DirectoryDiscovery')
            else:
                two_part_count += 1
                items.append(MediaFile(item_id, str(directory), find_ls=listing, attachments=attachments, issues=issues))
                item_log.write(Categories.Batch.DISCOVERY, Names.TWO_PARTS_DETECTED,
                               {'media_file_a': media[0], 'media_file_b': media[1]}, source='DirectoryDiscovery')
        workspace.check_stop(batch.id)
        workspace.append_directories(batch, items, log.prepare(
            Categories.Batch.DISCOVERY, Names.DIRECTORIES_SCANNED,
            {'two_part_movies': two_part_count, 'dated_movie_directories': dated_count}, source='DirectoryDiscovery'))

    @staticmethod
    def filename_year(path: str) -> int | None:
        stem = Path(path).stem.strip()
        # Prefer the trailing year when a title itself starts with a number.
        trailing = re.search(r'(?<![A-Za-z0-9])([0-9]{4})[)\]}]*$', stem)
        leading = re.match(r'^[([{]*([0-9]{4})(?![A-Za-z0-9])', stem)
        match = trailing or leading
        return int(match.group(1)) if match else None

    @staticmethod
    def subtitle_associations(media: list[str], subtitles: list[str]) -> dict[str, str | None]:
        associations = {}
        for subtitle in subtitles:
            path = Path(subtitle)
            same_folder = [video for video in media if Path(video).parent == path.parent]
            folder_subtitles = [other for other in subtitles if Path(other).parent == path.parent]
            basename_matches = [video for video in media if Path(video).stem.casefold() == path.stem.casefold()]
            local_matches = [video for video in basename_matches if video in same_folder]
            candidates = local_matches or basename_matches
            if not candidates and len(same_folder) == 1 and len(folder_subtitles) == 1:
                candidates = same_folder
            associations[subtitle] = candidates[0] if len(candidates) == 1 else None
        # Two subtitles targeting the same video would collide after renaming.
        counts = Counter(video for video in associations.values() if video is not None)
        return {subtitle: video if counts[video] == 1 else None
                for subtitle, video in associations.items()}

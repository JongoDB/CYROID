# backend/cyroid/services/msel_parser.py
import re
from typing import List, Dict, Any, Optional

import yaml


class MSELParser:
    """Parses MSEL markdown documents into structured inject definitions."""

    TIME_PATTERN = re.compile(r'^##\s+T\+(\d+):(\d+)\s+-\s+(.+)$', re.MULTILINE)
    PLACE_FILE_PATTERN = re.compile(
        r'-\s+Place file:\s+(\S+)\s+on\s+(\S+)\s+at\s+(.+)$',
        re.MULTILINE
    )
    RUN_COMMAND_PATTERN = re.compile(
        r'-\s+Run command on\s+(\S+):\s+(.+)$',
        re.MULTILINE
    )

    def parse(self, content: str) -> List[Dict[str, Any]]:
        """Parse MSEL markdown content into a list of inject definitions."""
        injects = []
        sections = self._split_into_sections(content)

        for seq, section in enumerate(sections, 1):
            inject = self._parse_section(section, seq)
            if inject:
                injects.append(inject)

        return injects

    def _split_into_sections(self, content: str) -> List[str]:
        """Split content into sections by ## T+ headers."""
        sections = []
        current: List[str] = []

        for line in content.split('\n'):
            if line.startswith('## T+'):
                if current:
                    sections.append('\n'.join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append('\n'.join(current))

        return sections

    def _parse_section(self, section: str, sequence: int) -> Optional[Dict[str, Any]]:
        """Parse a single section into an inject definition."""
        time_match = self.TIME_PATTERN.search(section)
        if not time_match:
            return None

        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        title = time_match.group(3).strip()

        # Extract description (text between title and Actions)
        desc_start = section.find('\n', time_match.end())
        desc_end = section.find('**Actions:**')
        description = ''
        if desc_end > desc_start:
            description = section[desc_start:desc_end].strip()

        # Parse actions
        actions = []

        for match in self.PLACE_FILE_PATTERN.finditer(section):
            actions.append({
                'action_type': 'place_file',
                'parameters': {
                    'filename': match.group(1),
                    'target_vm': match.group(2),
                    'target_path': match.group(3).strip()
                }
            })

        for match in self.RUN_COMMAND_PATTERN.finditer(section):
            actions.append({
                'action_type': 'run_command',
                'parameters': {
                    'target_vm': match.group(1),
                    'command': match.group(2).strip()
                }
            })

        return {
            'sequence_number': sequence,
            'inject_time_minutes': hours * 60 + minutes,
            'title': title,
            'description': description,
            'actions': actions
        }

    def parse_walkthrough(self, content: str) -> Optional[dict]:
        """Extract walkthrough section from MSEL content.

        Supports both pure YAML format and Markdown with YAML front matter.
        """
        # Try to parse as YAML first
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'walkthrough' in data:
                return self._validate_walkthrough(data['walkthrough'])
        except yaml.YAMLError:
            pass

        # Try to extract from YAML front matter (---\n...\n---)
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    front_matter = yaml.safe_load(parts[1])
                    if isinstance(front_matter, dict) and 'walkthrough' in front_matter:
                        return self._validate_walkthrough(front_matter['walkthrough'])
                except yaml.YAMLError:
                    pass

        return None

    def _validate_walkthrough(self, walkthrough: dict) -> Optional[dict]:
        """Validate walkthrough structure."""
        if not isinstance(walkthrough, dict):
            return None

        if 'title' not in walkthrough:
            return None

        if 'phases' not in walkthrough or not isinstance(walkthrough['phases'], list):
            return None

        for phase in walkthrough['phases']:
            if not isinstance(phase, dict):
                return None
            if 'id' not in phase or 'name' not in phase:
                return None
            if 'steps' not in phase or not isinstance(phase['steps'], list):
                return None
            for step in phase['steps']:
                if not isinstance(step, dict):
                    return None
                if 'id' not in step or 'title' not in step:
                    return None

        return walkthrough

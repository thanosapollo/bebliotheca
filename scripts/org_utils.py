"""Shared Org-mode utilities used by converters.

Provides common functions for generating Org-mode content, used by
convert_perseus_xml_to_org.py and convert_apostolic_to_org.py.
"""

import re
from typing import Dict, List


def add_custom_ids(org_text: str) -> str:
    """Add positional hN-hN CUSTOM_IDs to every Org heading.

    Mirrors thanos/org-add-custom-ids: each heading gets a hierarchical
    ID based on its position among siblings at each depth level.
    Replaces any existing CUSTOM_ID in PROPERTIES drawers.
    """
    lines = org_text.split('\n')
    result: List[str] = []
    counters: Dict[int, int] = {}
    i = 0

    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\*+)\s', line)

        if m:
            depth = len(m.group(1))
            counters[depth] = counters.get(depth, 0) + 1
            for d in list(counters):
                if d > depth:
                    del counters[d]
            custom_id = '-'.join(
                f'h{counters[d]}' for d in sorted(counters) if d <= depth
            )

            result.append(line)
            i += 1

            # Check for existing PROPERTIES drawer
            if i < len(lines) and lines[i].strip() == ':PROPERTIES:':
                i += 1  # skip :PROPERTIES:
                other_props: List[str] = []
                while i < len(lines) and lines[i].strip() != ':END:':
                    if ':CUSTOM_ID:' not in lines[i]:
                        other_props.append(lines[i])
                    i += 1
                i += 1  # skip :END:
                result.append(':PROPERTIES:')
                result.append(f':CUSTOM_ID: {custom_id}')
                result.extend(other_props)
                result.append(':END:')
            else:
                # Insert new PROPERTIES drawer
                result.append(':PROPERTIES:')
                result.append(f':CUSTOM_ID: {custom_id}')
                result.append(':END:')
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)

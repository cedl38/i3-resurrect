import os
import re
import sys
from pathlib import Path


def eprint(*args, **kwargs):
    """
    Function for printing to stderr.
    """
    print(*args, file=sys.stderr, **kwargs)


def filename_filter(filename):
    """
    Take a string and return a valid filename constructed from the string.
    """
    blacklist = '/\\:*"<>|'
    if filename is None:
        return filename

    # Remove blacklisted chars.
    for char in blacklist:
        filename = filename.replace(char, '')

    return filename


def list_filenames(directory):
    (_, _, filenames) = next(os.walk(directory))
    layout_regex = re.compile(r'.*_layout.json')
    layout_filenames = list(filter(layout_regex.search, filenames))
    programs_regex = re.compile(r'.*_programs.json')
    programs_filenames = list(filter(programs_regex.search, filenames))
    # Create a list of tuples to save workspace files
    files = []
    for n, layout_filename in enumerate(layout_filenames):
        layout_file = Path(directory) / layout_filename
        programs_file = Path(directory) / programs_filenames[n]
        files.append((layout_file, programs_file))
    return files

'''Commonly-used type and value definitions.'''


from enum import IntEnum
from enum import StrEnum
from pathlib import Path

import enum


REPOLIST_PATH = Path('./repolist.txt')
'''Path to text file listing URLs of code repositories to download.'''

REPODIR_PATH = Path('./repos')
'''Path to the directory where code repositories are stored.'''

CORPUSDIR_PATH = Path('./corpus')
'''Path to the directory where corpus data is stored.'''


class ConstructionStep(IntEnum):
    '''Steps of corpus construction.

    START: Before building corpus.
    DOWNLOAD: Downloading repos.
    EXTRACT: Extracting and tokenizing raw data from repos.
    ANNOTATE: Annotating utterances.
    END: After building corpus.

    '''
    START = enum.auto()
    DOWNLOAD = enum.auto()
    EXTRACT = enum.auto()
    ANNOTATE = enum.auto()
    END = enum.auto()

    @classmethod
    def from_string(cls, s):
        return {
            'start': cls.START,
            'download': cls.DOWNLOAD,
            'extract': cls.EXTRACT,
            'annotate': cls.ANNOTATE,
            'end': cls.END,
        }[s.lower()]


class NoteType(StrEnum):
    '''Types of source code annotations.

    COMMENT
    COMMIT_MESSAGE
    DOCUMENTATION

    '''
    COMMENT = 'comment'
    COMMIT_MESSAGE = 'commit-message'
    DOCUMENTATION = 'documentation'

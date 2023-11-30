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

BUILDNOTESDIR_PATH = Path('./build_notes')
'''Path to the directory where build notes are stored.'''

BUILDNOTES_INCLUDED_CODE_PATH = BUILDNOTESDIR_PATH / Path('comments_code_included.txt')
'''Path to the file that logs syntactically valid code that has been included in the corpus.'''

BUILDNOTES_EXCLUDED_CODE_PATH = BUILDNOTESDIR_PATH / Path('comments_code_excluded.txt')
'''Path to the file that logs syntactically valid code that has not been included in the corpus.'''


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

    CHANGELOG
    COMMENT
    DOCUMENTATION

    '''
    CHANGELOG = 'changelog'
    COMMENT = 'comment'
    DOCUMENTATION = 'documentation'

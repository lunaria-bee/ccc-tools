'''Commonly-used type and value definitions.'''


from enum import StrEnum
from pathlib import Path


REPOLIST_PATH = Path('./repolist.txt')
'''Path to text file listing URLs of code repositories to download.'''

REPODIR_PATH = Path('./repos')
'''Path to the directory where code repositories are stored.'''

CORPUSDIR_PATH = Path('./corpus')
'''Path to the directory where corpus data is stored.'''

FIELDS = (
    'category', # see CATEGORIES
    'token',    # raw text of the token
    'author',   # author of the text in the token
)
'''Field structure for each line of corpus CSV files.'''

ITEM_START = '<s>'
'''Item start control token.'''

ITEM_END = '</s>'
'''Item end control token'''


class Category(StrEnum):
    '''Token categories.

    TOKEN: Token from a text in the corpus.
    CONRTOL: Special token to indicate corpus structure.

    '''
    TOKEN = 'T'
    CONTROL = 'C'

'''Tools for corpus management.'''


from defines import CORPUSDIR_PATH
from defines import FIELDS
from defines import ITEM_END
from defines import ITEM_START
from defines import Category
from repo import RepoManager

from contextlib import ExitStack
from itertools import chain
from pathlib import Path

import nltk


def write_line_to_corpus_file(corpus_file, **kwargs):
    '''Write one line of a corpus to a file.

    Line fields accepted as keyword arguments, with argument names from defines.FIELDS.

    '''
    # corpus_file.write(f'{category},{token},{author}\n')
    corpus_file.write(",".join(
        kwargs[f] if f in kwargs.keys() else ''
        for f in FIELDS
    ))
    corpus_file.write("\n")


def write_utterance_to_corpus_file(corpus_file, utterance, **kwargs):
    '''Write a complete utterance of a corpus to a file.'''

    write_line_to_corpus_file(
        corpus_file,
        category=Category.CONTROL,
        token=ITEM_START,
    )

    for token in nltk.word_tokenize(utterance):
        write_line_to_corpus_file(
            corpus_file,
            category=Category.TOKEN,
            token=token,
            **kwargs,
        )

    write_line_to_corpus_file(
        corpus_file,
        category=Category.CONTROL,
        token=ITEM_END,
    )


def read_corpus_file(corpus_file):
    return [
        dict(zip(FIELDS, line.strip().split(',')))
        for line in corpus_file.readlines()
    ]


def get_corpus(repos=None, note_types=None, omit_tokens=False):
    '''Get whole corpus as list of dicts.

    TODO args

    Return: List of dicts, where each dict contains a token and its annotation data.

    '''
    if repos is None:
        repolist = RepoManager.get_repolist()
    else:
        repolist = []
        for r in repos:
            full_repolist = RepoManager.get_repolist()
            if isinstance(r, RepoManager):
                repolist.append(r)
            elif isinstance(r, str):
                repolist.append(next(repo for repo in full_repolist if repo.name==r))

    if note_types is None:
        note_types = ['commit_messages'] # rework note type naming & ID scheme

    corpus_paths = [
        CORPUSDIR_PATH / Path(f'{note_type}.{repo.name}.csv')
        for note_type in note_types
        for repo in repolist
    ]

    with ExitStack() as stack:
        files = [stack.enter_context(open(path)) for path in corpus_paths]
        corpus = list(chain.from_iterable(read_corpus_file(f) for f in files))

    return corpus

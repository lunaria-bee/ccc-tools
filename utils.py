'''Commonly-used helper functions.'''


from defines import Category
from defines import ITEM_END
from defines import ITEM_START

from nltk import word_tokenize

import re


def get_repo_name_from_url(url):
    '''Use reposiroty URL to determine repository name.'''
    match = re.fullmatch(r'.*/(.*?).git', url)

    if match:
        return match.group(1)
    else:
        raise ValueError(f"Could not interpret '{url}' as repository URL.")


def write_line_to_corpus_file(
        corpus_file,
        category='',
        token='',
        author='',
):
    '''Write one line of a corpus to a file.'''
    corpus_file.write(f'{category},{token},{author}\n')


def write_utterance_to_corpus_file(
        corpus_file,
        utterance,
        author='',
):
    '''Write a complete utterance of a corpus to a file.'''

    write_line_to_corpus_file(
        corpus_file,
        category=Category.CONTROL,
        token=ITEM_START,
    )

    for token in word_tokenize(utterance):
        write_line_to_corpus_file(
            corpus_file,
            category=Category.TOKEN,
            token=token,
            author=author,
        )

    write_line_to_corpus_file(
        corpus_file,
        category=Category.CONTROL,
        token=ITEM_END,
    )

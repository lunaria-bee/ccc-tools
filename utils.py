'''Commonly-used helper functions.'''


from defines import Category
from defines import ITEM_END
from defines import ITEM_START
from defines import REPODIR_PATH
from defines import REPOLIST_PATH

from nltk import word_tokenize
from pathlib import Path

import git
import logging
import os
import re
import shutil


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


class RepoManager:
    '''Manage data and git interactions for a repository.'''

    def __init__(self, url):
        self._url = url
        self._name = RepoManager.get_name_from_url(url)
        # self._commit # TODO
        self._dir = REPODIR_PATH / Path(self._name)
        self._git = None

    def __str__(self):
        return self._name

    @staticmethod
    def get_repolist(repolist_path=REPOLIST_PATH):
        '''Get list of RepoManager objects created from repolist file.'''
        with open(repolist_path) as repolist_file:
            repolist = [RepoManager(url) for url in [line.strip() for line in repolist_file.readlines()]]

        return repolist

    @staticmethod
    def get_name_from_url(url):
        '''Use reposiroty URL to determine repository name.'''
        match = re.fullmatch(r'.*/(.*?).git', url)

        if match:
            return match.group(1)
        else:
            raise ValueError(f"Could not interpret '{url}' as repository URL.")

    def is_available(self):
        '''Has the repository been downloaded?

        Just checks that the path at self.dir is a directory with some contents; does not
        check that those conetnts form a valid repository.

        '''
        return self._dir.is_dir() and os.listdir(self._dir)

    def download(self, force_redownload=False):
        '''Download the repository from data at its URL.

        If the path at `self.dir` is a populated directory, this function assumes that the
        repository has already been downloaded, ans skips it unless `force_redownload` is
        `True`.

        skip_redownload: Download repository even if directory at self.dir is populated.

        '''
        download = True
        if self.is_available():
            if force_redownload:
                logging.debug(f"{self._name}: Forcing redownload")
                shutil.rmtree(self._dir)
                download = True
            else:
                logging.debug(f"{self._name}: Already downloaded")
                download = False

        if download:
            logging.debug(f"{self._name}: Downloading...")
            git.Repo.clone_from(self._url, self._dir)
            logging.debug(f"{self._name}: Done.")

        return download

    @property
    def url(self):
        '''URL to download the repository from.'''
        return self._url

    @property
    def name(self):
        '''Name of the repository.'''
        return self._name

    @property
    def dir(self):
        '''Path to directory containing the repository.'''
        return self._dir

    @property
    def git(self):
        '''git.Repo object for version control interactions.'''
        if self._git is None:
            if not self.is_available():
                self.download()

            self._git = git.Repo(self._dir)

        return self._git

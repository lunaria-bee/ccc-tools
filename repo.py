'''Tools for repository management.'''


from defines import REPODIR_PATH
from defines import REPOLIST_PATH

from pathlib import Path

import collections
import git
import logging
import os
import re
import shutil


class RepoManager:
    '''Manage data and git interactions for a repository.'''

    def __init__(self, url, rev='HEAD'):
        self._url = url
        self._rev = rev
        self._name = RepoManager.get_name_from_url(url)
        # self._commit # TODO
        self._dir = REPODIR_PATH / Path(self._name)
        self._git = None
        self._git_cmd = None

    def __str__(self):
        return self._name

    def __repr__(self):
        return f"RepoManager({self._name})"

    @staticmethod
    def get_repolist(repolist_path=REPOLIST_PATH):
        '''Get list of RepoManager objects created from repolist file.'''
        with open(repolist_path) as repolist_file:
            repolist = [
                RepoManager(url, rev)
                for url, rev
                in [
                    line.strip().split(',')
                    for line in repolist_file.readlines()
                    if not line.startswith('#')
                ]
            ]

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
            logging.debug(f"{self._name}: Switching to revision {self._rev}")
            self.git_cmd.checkout(self._rev)
            logging.debug(f"{self._name}: Done.")

        return download

    @property
    def url(self):
        '''URL to download the repository from.'''
        return self._url

    @property
    def rev(self):
        '''Revision of the repository to checkout.'''
        return self._rev

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
        '''git.Repo object for version control information access.'''
        if self._git is None:
            if not self.is_available():
                self.download()

            self._git = git.Repo(self._dir)

        return self._git

    @property
    def git_cmd(self):
        '''git.cmd.Git object for git binary interactions.'''
        if self._git_cmd is None:
            self._git_cmd = git.cmd.Git(self._dir)

        return self._git_cmd


class _BlameIndexEntry:
    '''TODO'''

    def __init__(self, commit, line):
        self._commit = commit
        self._line = line

    @property
    def commit(self):
        return self._commit

    @property
    def line(self):
        return self._line


_BlameIndexEntry = collections.namedtuple('_BlameIndexEntry', ('commit', 'line'))
'''TODO'''


class BlameIndex:
    '''TODO'''

    def __init__(self, repo, rev, path):
        self._raw_blame = repo.git.blame(rev, path)
        self._repo = repo
        self._rev = rev
        self._path = path

        self._index = []
        for commit, lines in self._raw_blame:
            for line in lines:
                self._index.append(_BlameIndexEntry(commit, line))

    def __len__(self):
        return len(self._index)

    def __getitem__(self, key):
        # Lines index from 1, list indexes from 0; decrement all indices by 1.
        if isinstance(key, slice):
            return self._index[slice(key.start-1, key.stop-1, key.step)]
        else:
            return self._index[key-1]

    def search(self, string):
        '''Return first index entry whose line contains `string`.'''
        for i, entry in self._index:
            if string in entry.line:
                return entry

    def find_all(self, string):
        '''Return all index entries whose line contains `string`.'''
        return [
            entry for entry in self._index
            if string in entry.line
        ]

    @property
    def raw_blame(self):
        '''TODO'''
        return self._raw_blame

    @property
    def repo(self):
        '''TODO'''
        return self._repo

    @property
    def rev(self):
        '''TODO'''
        return self._rev

    @property
    def path(self):
        '''TODO'''
        return self._path

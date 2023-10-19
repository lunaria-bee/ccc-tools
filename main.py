#!/usr/bin/env python3


from defines import CORPUSDIR_PATH
from defines import ITEM_END
from defines import ITEM_START
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from utils import RepoManager
from utils import write_utterance_to_corpus_file

from git import Repo
from pathlib import Path

import logging
import re
import sys


def download_repos():
    '''Download repositories listed in repolist.txt.'''

    logging.info("Retrieving repos...")

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")
        downloaded = repo.download()

    logging.info("Finished retrieving repos.")


def extract_data():
    '''Extract data from downloaded repos.'''

    logging.info("Extracting data...")

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    for repo in RepoManager.get_repolist():
        commit_messages_path = CORPUSDIR_PATH / Path(f'commit_messages.{repo.name}.csv')

        logging.info(f" {repo.name}")

        # Write commits.
        with open(commit_messages_path, 'w') as commit_messages_file:
            commit_count = len(list(repo.git.iter_commits()))
            for i, commit in enumerate(repo.git.iter_commits()):
                logging.debug(f"{repo.name} commit {i}/{commit_count}")
                write_utterance_to_corpus_file(
                    commit_messages_file,
                    commit.message,
                    author=commit.author,
                )

    logging.info("Finished extracting data.")


def main(argv):
    # Setup logging.
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.INFO)

    # Build corpus.
    download_repos()
    extract_data()
    # TODO Annotate data

    pass


if __name__== '__main__': main(sys.argv)

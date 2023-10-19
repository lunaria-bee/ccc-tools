#!/usr/bin/env python3


from defines import CORPUSDIR_PATH
from defines import ITEM_END
from defines import ITEM_START
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from utils import get_repo_name_from_url
from utils import write_utterance_to_corpus_file

from git import Repo
from pathlib import Path

import logging
import re
import sys


def download_repos():
    '''Download repositories listed in repolist.txt.'''

    logging.info("Retrieving repos...")

    with open(REPOLIST_PATH) as repolist_file:
        repolist_urls = [line.strip() for line in repolist_file.readlines()]

    for repo_url in repolist_urls:
        repo_name = get_repo_name_from_url(repo_url)
        repo_dir = REPODIR_PATH / Path(repo_name)
        if repo_dir.exists():
            logging.info(f"Skipping {repo_name}: Already downloaded.")
        if not repo_dir.exists():
            logging.info(f"Downloading {repo_name} from {repo_url}...")
            Repo.clone_from(repo_url, repo_dir)

    logging.info("Finished retrieving repos.")


def extract_data():
    '''Extract data from downloaded repos.'''

    logging.info("Extracting data...")

    with open(REPOLIST_PATH) as repolist_file:
        repolist_urls = [line.strip() for line in repolist_file.readlines()]

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    for repo_url in repolist_urls:
        repo_name = get_repo_name_from_url(repo_url)
        repo_dir = REPODIR_PATH / Path(repo_name)
        commit_messages_path = CORPUSDIR_PATH / Path(f'commit_messages.{repo_name}.csv')

        logging.info(f"From {repo_name}...")

        repo = Repo(repo_dir)

        # Write commits.
        with open(commit_messages_path, 'w') as commit_messages_file:
            commit_count = len(list(repo.iter_commits()))
            for i, commit in enumerate(repo.iter_commits()):
                logging.debug(f"{repo_name} commit {i}/{commit_count}")
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

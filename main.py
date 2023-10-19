#!/usr/bin/env python3


from defines import REPOLIST_PATH
from defines import REPODIR_PATH

from git import Repo
from pathlib import Path

import logging
import re
import sys


def download_repos():
    logging.info("Retrieving repos...")

    with open(REPOLIST_PATH) as repolist_file:
        repolist_urls = [line.strip() for line in repolist_file.readlines()]

    for repo_url in repolist_urls:
        repo_name = re.fullmatch(r'.*/(.*?).git', repo_url).group(1)
        repo_dir = REPODIR_PATH / Path(repo_name)
        if repo_dir.exists():
            logging.info(f"Skipping {repo_name}: Already downloaded.")
        if not repo_dir.exists():
            Repo.clone_from(repo_url, repo_dir)

    logging.info("Finished retrieving repos.")


def main(argv):
    # Setup logging.
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.INFO)

    # Build corpus.
    download_repos()

    # TODO Extract data

    # TODO Annotate data

    pass


if __name__== '__main__': main(sys.argv)

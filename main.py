#!/usr/bin/env python3


from defines import CORPUSDIR_PATH
from defines import ITEM_END
from defines import ITEM_START
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from utils import RepoManager
from utils import write_utterance_to_corpus_file

from argparse import ArgumentParser
from pathlib import Path

import logging
import re
import sys


parser = ArgumentParser()

parser.add_argument(
    '-v',
    action='store_true',
    help="Print more logging output to stderr.",
)

parser.add_argument(
    '-V',
    action='store_true',
    help="Print less logging output to stderr.",
)

parser.add_argument(
    '-q',
    action='store_true',
    help="Do not print any logging output to stderr.",
)

parser.add_argument(
    '-d',
    action='store_true',
    help=(
        "Print as much logging output to stderr as with -v, plus include detailed"
        + " log annotations in each line of logging output."
    ),
)


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
                write_utterance_to_corpus_file(
                    commit_messages_file,
                    commit.message,
                    author=commit.author,
                )

    logging.info("Finished extracting data.")


def main(argv):
    args = parser.parse_args(argv[1:])

    # Validate arguments.
    if (args.v or args.d) and (args.V or args.q):
        raise ValueError(
            f"Incompatible opts {'-v' if args.v else '-d'} and {'-V' if args.V else '-q'}"
        )

    # Process arguments.
    log_level = logging.INFO
    debug_output = False
    enable_logging = True

    if args.v:
        log_level = logging.DEBUG

    if args.d:
        log_level = logging.DEBUG
        debug_output = True

    if args.V:
        log_level = logging.WARNING

    if args.q:
        enable_logging = False

    # Setup logging.
    if enable_logging:
        handler = logging.StreamHandler()
        if debug_output:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(filename)s:%(lineno)d] [%(levelname)s] %(message)s"
            ))

        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(log_level)

    # Build corpus.
    download_repos()
    extract_data()
    # TODO Annotate data

    pass


if __name__== '__main__': main(sys.argv)

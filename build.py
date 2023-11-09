#!/usr/bin/env python3


from defines import ConstructionStep
from defines import NoteType
from defines import CORPUSDIR_PATH
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from repo import RepoManager

from argparse import ArgumentParser
from hashlib import sha1 as name_hash
from pathlib import Path
from xml.etree import ElementTree

import logging
import re
import sys


parser = ArgumentParser()

parser.add_argument(
    '--redo',
    action='store_true',
    help="Rebuild entire corpus.",
)

parser.add_argument(
    '--redo-from',
    choices=('download', 'extract', 'annotate'),
    help=(
        "Partially rebuild corpus beginning from a particular step."
        + " Not currently implemented for 'extract' or 'annotate'."
    ),
)

# TODO implement extract redo
# TODO implement annotate redo

# TODO implement
# parser.add_argument(
#     '--redo-annotation',
#     help="Partially re-annotate corpus.",
# )

parser.add_argument(
    '-v',
    action='store_true',
    help="Print more logging output to stderr.",
)

parser.add_argument(
    '-d',
    action='store_true',
    help=(
        "Print as much logging output to stderr as with -v, plus include detailed"
        + " log annotations in each line of logging output."
    ),
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


def download_repos(force_redownload=False):
    '''Download repositories listed in repolist.txt.'''

    logging.info("Retrieving repos...")

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")
        downloaded = repo.download(force_redownload)

    logging.info("Finished retrieving repos.")


def extract_data():
    '''Extract data from downloaded repos.'''

    logging.info("Extracting data...")

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")

        commit_messages_root = ElementTree.Element('notes')
        for commit in repo.git.iter_commits():
            ElementTree.SubElement(
                commit_messages_root,
                'note',
                text=commit.message,
                attrib={
                    'author': name_hash(commit.author.name.encode('utf-8')).hexdigest(),
                    'repo': repo.name,
                    # TODO revision
                    'note-type': NoteType.COMMIT_MESSAGE,
                }
            )

        commit_messages_tree = ElementTree.ElementTree(commit_messages_root)
        commit_messages_tree.write(CORPUSDIR_PATH / Path(f'commit_messages.{repo.name}.xml'))

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
    enable_debug_output = False
    enable_logging = True
    redo_level = ConstructionStep.END

    if args.v:
        log_level = logging.DEBUG

    if args.d:
        log_level = logging.DEBUG
        enable_debug_output = True

    if args.V:
        log_level = logging.WARNING

    if args.q:
        enable_logging = False

    if args.redo_from:
        redo_level = ConstructionStep.from_string(args.redo_from)

    if args.redo:
        redo_level = ConstructionStep.START

    # Setup logging.
    if enable_logging:
        handler = logging.StreamHandler()
        if enable_debug_output:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(filename)s:%(lineno)d] [%(levelname)s] %(message)s"
            ))

        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(log_level)

    # Build corpus.
    download_repos(force_redownload=(redo_level<=ConstructionStep.DOWNLOAD))
    extract_data()
    # TODO Annotate data

    pass


if __name__== '__main__': main(sys.argv)

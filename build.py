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
#     '--redo-extract',
#     help="Partially re-extract corpus data.",
# )

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


def normalize_string(s):
    '''Correct irregularities in string content.'''
    # Strip bell character (unicode x07) from string.
    return s.translate({7: ''})


def download_repos(force_redownload=False):
    '''Download repositories listed in repolist.txt.

    force_redownload: Whether to redownload previously downloaded repositories.

    '''

    logging.info("Retrieving repos...")

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")
        downloaded = repo.download(force_redownload)

    logging.info("Finished retrieving repos.")


def extract_data(force_reextract=()):
    '''Extract data from downloaded repos.

    force_reextract: Iterable of NoteType values. Data of these types will be extracted
    from repos, even if that data has been extracted before.

    '''

    logging.info("Extracting data...")

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")

        commit_messages_path = CORPUSDIR_PATH / Path(f'commit_messages.{repo.name}.xml')

        # Only extract data if corpus file does not exist or if we are forced to by
        # force_reextract.
        if (
                NoteType.COMMIT_MESSAGE in force_reextract
                or not commit_messages_path.exists()
        ):
            commit_messages_root = ElementTree.Element('notes')
            for commit in repo.git.iter_commits():
                note = ElementTree.SubElement(
                    commit_messages_root,
                    'note',
                    author=name_hash(commit.author.name.encode('utf-8')).hexdigest(),
                    repo=repo.name,
                    # TODO revision
                    note_type=NoteType.COMMIT_MESSAGE,
                )
                note.text = normalize_string(commit.message)

            commit_messages_tree = ElementTree.ElementTree(commit_messages_root)
            commit_messages_tree.write(
                commit_messages_path,
                encoding='utf-8',
                xml_declaration=True,
            )

    logging.info("Finished extracting data.")


def main(argv):
    args = parser.parse_args(argv)

    # Validate arguments.
    if (args.v or args.d) and (args.V or args.q):
        raise ValueError(
            f"Incompatible opts {'-v' if args.v else '-d'} and {'-V' if args.V else '-q'}."
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

    # Download
    redo_download = (redo_level <= ConstructionStep.DOWNLOAD)
    download_repos(force_redownload=redo_download)

    # Extract.
    if redo_level <= ConstructionStep.EXTRACT:
        redo_note_types = tuple(NoteType)
    else:
        redo_note_types = tuple()

    extract_data(force_reextract=redo_note_types)

    # TODO Annotate.


if __name__== '__main__': main(sys.argv[1:])

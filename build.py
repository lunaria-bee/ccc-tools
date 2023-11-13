#!/usr/bin/env python3


from defines import ConstructionStep
from defines import NoteType
from defines import CORPUSDIR_PATH
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from repo import RepoManager

from argparse import ArgumentParser
from hashlib import sha256 as anon_hash
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


def anonymize_id(s):
    '''Hash an identifying string to anonymize it.'''
    return anon_hash(s.encode('utf-8')).hexdigest()[:16]


def download_repos(force_redownload=False):
    '''Download repositories listed in repolist.txt.

    force_redownload: Whether to redownload previously downloaded repositories.

    '''

    logging.info("Retrieving repos...")

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")
        downloaded = repo.download(force_redownload)

    logging.info("Finished retrieving repos.")


def _create_comment_subelement(parent, text, authors, repo):
    '''TODO'''
    elt = ElementTree.SubElement(
        parent,
        'note',
        attrib={
            'author': ','.join(authors), # TODO improve XML for multiple authors
            'repo': repo.name,
            # TODO revision
            'note-type': NoteType.COMMENT,
        }
    )
    elt.text = text

    return elt


def _accumulate_comment_author_pairs_from_source_file(path, repo):
    '''TODO'''
    comment = ""
    authors = set()
    last_line_had_comment = False
    comment_author_pairs = []
    for commit, lines in repo.git.blame('HEAD', path.relative_to(repo.dir)):
        for line in lines:
            match = re.search(r'(#.*)$', line)
            if match:
                if last_line_had_comment:
                    # Continue accumulating comment.
                    comment += f"{match.group(1)}\n"
                    authors.add(anonymize_id(commit.author.name))
                else:
                    # Create node for previously accumulated comment.
                    # TODO Filter commented code.
                    comment_author_pairs.append((comment, authors))

                    # Start accumulating new comment.
                    comment = f"{match.group(1)}\n"
                    authors = {anonymize_id(commit.author.name)}

                    last_line_had_comment = True

            else:
                last_line_had_comment = False

    return comment_author_pairs


def _create_repo_comments_xml_tree(repo):
    '''TODO'''
    root = ElementTree.Element('notes')
    for source_path in repo.dir.glob('**/*.py'):
        comment_author_pairs = _accumulate_comment_author_pairs_from_source_file(source_path, repo)

        for comment, authors in comment_author_pairs:
            _create_comment_subelement(root, comment, authors, repo)

    return ElementTree.ElementTree(root)


def extract_data(force_reextract=()):
    '''Extract data from downloaded repos.

    force_reextract: Iterable of NoteType values. Data of these types will be extracted
    from repos, even if that data has been extracted before.

    '''

    logging.info("Extracting data...")

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")

        # Extract changelogs.
        logging.debug(f"  {NoteType.CHANGELOG}")
        changelogs_path = CORPUSDIR_PATH / Path(f'{NoteType.CHANGELOG}.{repo.name}.xml')
        if (
                NoteType.CHANGELOG in force_reextract
                or not changelogs_path.exists()
        ):
            changelogs_root = ElementTree.Element('notes')
            for commit in repo.git.iter_commits():
                note = ElementTree.SubElement(
                    changelogs_root,
                    'note',
                    attrib={
                        'author': anonymize_id(commit.author.name), # TODO anonymize other name occurrences
                        'repo': repo.name,
                        # TODO revision
                        'note_type': NoteType.CHANGELOG,
                    }
                )
                note.text = normalize_string(commit.message)

            changelogs_tree = ElementTree.ElementTree(changelogs_root)
            changelogs_tree.write(
                changelogs_path,
                encoding='utf-8',
                xml_declaration=True,
            )

        # Extract comments.
        logging.debug(f"  {NoteType.COMMENT}")
        comments_path = CORPUSDIR_PATH / Path(f'{NoteType.COMMENT}.{repo.name}.xml')
        if (
                NoteType.COMMENT in force_reextract
                or not comments_path.exists()
        ):
            comments_tree = _create_repo_comments_xml_tree(repo)
            comments_tree.write(
                comments_path,
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

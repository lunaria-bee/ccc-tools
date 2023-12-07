#!/usr/bin/env python3


from defines import ConstructionStep
from defines import NoteType
from defines import BUILDNOTESDIR_PATH
from defines import BUILDNOTES_INCLUDED_CODE_PATH
from defines import BUILDNOTES_EXCLUDED_CODE_PATH
from defines import CORPUSDIR_PATH
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from repo import BlameIndex
from repo import RepoManager

from argparse import ArgumentParser
from hashlib import sha256 as anon_hash
from nltk.tag import pos_tag
from nltk.tokenize import sent_tokenize
from nltk.tokenize import word_tokenize
from pathlib import Path
from xml.etree import ElementTree

import ast
import collections
import logging
import re
import shutil
import sys
import tokenize


# TODO precompile regexes


_CommentAuthorPair = collections.namedtuple('_CommentAuthorPair', ('comment', 'authors'))


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


def strip_comment_delimiters(comment):
    '''TODO'''
    return "\n".join(
        line.lstrip('#') for line in comment.split('\n')
    )


def trim_comment_as_code(comment):
    '''Trim comment delimiters and leading whitespace, preserving indentation.

    For this function to work, indentations *cannot* mix tabs and spaces.

    '''
    # Remove comment delimiters
    comment = strip_comment_delimiters(comment)

    # Find amount of whitespace to remove. Result is smallest number of leading
    # spaces/tabs on a line.
    consistent_whitespace_regex = re.compile(r'( +|\t+)')
    whitespace_width = float('inf')
    for line in comment.split('\n'):
        match = consistent_whitespace_regex.match(line)
        if match and len(match.group()) < whitespace_width:
            whitespace_width = len(match.group())

    # Trim whitespace.
    if whitespace_width != float('inf'):
        comment = "\n".join(
            line[whitespace_width:] for line in comment.split("\n")
        )

    return comment


def ast_contains(tree, node_type):
    '''Does `tree` contain a node of `node_type`?'''
    if isinstance(tree, node_type):
        return True

    else:
        return any(
            ast_contains(node, node_type)
            for node in ast.iter_child_nodes(tree)
        )


def is_comment_code(comment):
    '''Is `comment` just commented out code?

    This function does not simply check whether the comment is syntactically valid
    code. For comments that are syntactically valid code, it also tries to determine
    whether the comment is natural language that also happens to be syntactically valid
    code. To be considered natural language, a syntactically valid code snippet must...

    - ...*not* contain *any* of the following characters: '(', ')', '[', ']', '=', '.'
    - ...*not* contain the text "return"

    '''
    trimmed_comment = trim_comment_as_code(comment)

    try:
        tree = ast.parse(trimmed_comment)

        # Check if the comment, despite being valid code, is still something we want to
        # interpret as English (alphanumeric strings optionally separated by operators).
        if (
                not set('()[]=.').intersection(set(trimmed_comment))
                and 'return' not in trimmed_comment
        ):
            return False

        # If all checks pass, is probably code.
        return True

    except SyntaxError:
        return False


def _accumulate_comment_author_pairs_from_source_file(path, repo):
    '''TODO'''
    comment = ""
    authors = set()
    last_line_had_comment = False
    first_comment_found = False
    comment_author_pairs = []

    blame_index = BlameIndex(repo, 'HEAD', path.relative_to(repo.dir))
    last_line_with_comment = 0 # tokenize functions index lines from 1

    with tokenize.open(path) as source_file:
        for token in tokenize.generate_tokens(source_file.readline):
            if token.type == tokenize.COMMENT:

                if last_line_with_comment == token.start[0]-1:
                    # Continuation of previous comment.
                    comment += f"{token.string}\n"
                    for blame in blame_index[token.start[0]:token.end[0]+1]:
                        authors.add(anonymize_id(blame.commit.author.name))

                else:
                    # New comment.
                    if last_line_with_comment != 0:
                        # Accumulate previous comment.
                        if is_comment_code(comment):
                            try:
                                ast.parse(trim_comment_as_code(comment))
                                with open(BUILDNOTES_EXCLUDED_CODE_PATH, 'a') as f:
                                    f.write(comment)
                                    f.write(f"{'<>'*32}\n")
                            except SyntaxError:
                                pass
                        else:
                            try:
                                ast.parse(trim_comment_as_code(comment))
                                with open(BUILDNOTES_INCLUDED_CODE_PATH, 'a') as f:
                                    f.write(comment)
                                    f.write(f"{'<>'*32}\n")
                            except SyntaxError:
                                pass

                        comment_author_pairs.append(_CommentAuthorPair(comment, authors))

                    comment = f"{token.string}\n"
                    authors = set(
                        anonymize_id(blame.commit.author.name)
                        for blame in blame_index[token.start[0]:token.end[0]+1]
                    )

                last_line_with_comment = token.end[0]

    return comment_author_pairs


def _create_note_subelement(parent, text, authors, note_type, repo):
    '''TODO'''
    note_elt = ElementTree.SubElement(
        parent,
        'note',
        attrib={
            'author': ','.join(authors), # TODO improve XML for multiple authors
            'repo': repo.name,
            'revision': repo.rev,
            'note-type': note_type,
        }
    )

    # XML element for raw text.
    raw_elt = ElementTree.SubElement(note_elt, 'raw')
    raw_elt.text = text

    # Tokenize text. Strip delimiters from comments.
    if note_type == NoteType.COMMENT:
        stripped_text = strip_comment_delimiters(text)
        sents = [word_tokenize(sent) for sent in sent_tokenize(stripped_text)]
    else:
        sents = [word_tokenize(sent) for sent in sent_tokenize(text)]

    # XML element for tokens, separated by spaces, with sents separated by newlines.
    tokens_elt = ElementTree.SubElement(note_elt, 'tokens')
    tokens_elt.text = "\n".join(" ".join(token for token in sent) for sent in sents)

    # XML element for POS tags, aligned to tokens, with same space/newline separation
    # scheme.
    pos_elt = ElementTree.SubElement(note_elt, 'pos')
    pos_elt.text = "\n".join(" ".join(t[1] for t in pos_tag(sent)) for sent in sents)

    return note_elt


def _create_repo_comments_xml_tree(repo):
    '''TODO'''
    root = ElementTree.Element('notes')
    for source_path in repo.dir.glob('**/*.py'):
        comment_author_pairs = _accumulate_comment_author_pairs_from_source_file(source_path, repo)

        for comment, authors in comment_author_pairs:
            _create_note_subelement(root, comment, authors, NoteType.COMMENT, repo)

    return ElementTree.ElementTree(root)


def extract_data(force_reextract=()):
    '''Extract data from downloaded repos.

    force_reextract: Iterable of NoteType values. Data of these types will be extracted
    from repos, even if that data has been extracted before.

    '''

    logging.info("Extracting data...")

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    # Remove build_notes directory (if it exists).
    if (
            NoteType.COMMENT in force_reextract
            and BUILDNOTESDIR_PATH.is_dir()
    ):
        shutil.rmtree(BUILDNOTESDIR_PATH)
        BUILDNOTESDIR_PATH.mkdir()

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
                if commit.message:
                    _create_note_subelement(
                        changelogs_root,
                        normalize_string(commit.message),
                        [anonymize_id(commit.author.name)],
                        NoteType.CHANGELOG,
                        repo
                    )

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

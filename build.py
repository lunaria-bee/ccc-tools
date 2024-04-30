#!/usr/bin/env python3


# TODO clean up imports

from defines import ConstructionStep
from defines import Language
from defines import NoteType
from defines import BUILDNOTESDIR_PATH
from defines import BUILDNOTES_INCLUDED_CODE_PATH
from defines import BUILDNOTES_EXCLUDED_CODE_PATH
from defines import CORPUSDIR_PATH
from defines import LIBCLANG_HEADER_PATH
from defines import REPOLIST_PATH
from defines import REPODIR_PATH
from repo import BlameIndex
from repo import RepoManager

from argparse import ArgumentParser
from collections import deque
from collections import namedtuple
from hashlib import sha256 as anon_hash
from nltk.tag import pos_tag
from nltk.tokenize import sent_tokenize
from nltk.tokenize import word_tokenize
from pathlib import Path
import threading
from threading import Thread
from xml.etree import ElementTree

import ast
import clang.cindex
import itertools as itr
import logging
import multiprocessing as mp
import re
import shutil
import sys
import tokenize


# TODO precompile regexes


_CommentAuthorPair = namedtuple('_CommentAuthorPair', ('comment', 'authors'))
_TextPos = namedtuple('_TextPos', ('line', 'column'))


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
        " Not currently implemented for 'annotate'."
    ),
)

parser.add_argument(
    '--note-types',
    choices=tuple(NoteType),
    nargs='+',
    help=(
        "Only process selected note types."
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

parser.add_argument(
    '--build-notes',
    action='store_true',
    help="Write information about corpus construction to build_notes directory.",
)


WRITE_BUILD_NOTES = False


class TokenizationError(Exception):
    pass


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


def strip_comment_delimiters(comment, language):
    '''Remove comment delimiters from `comment`.

    `language` parameter is used to determine what comment delimiters will look like and
    how to remove them.

    '''
    if language in (Language.C, Language.CPP):
        # TODO strip excess '*'
        # TODO more intelligent stripping for multiline-style comments ("/*...*/")
        return "\n".join(
            line.lstrip('//').lstrip('/*').rstrip('*/') for line in comment.split('\n')
        )

    elif language==Language.PYTHON:
        return "\n".join(
            line.lstrip('#') for line in comment.split('\n')
        )


def trim_comment_as_code(comment, language):
    '''Trim comment delimiters and leading whitespace, preserving indentation.

    For this function to work, indentations *cannot* mix tabs and spaces.

    '''
    # Remove comment delimiters
    comment = strip_comment_delimiters(comment, language)

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


def validate_source_text_language(text, language=None):
    '''Determine whether `text` is valid code in some programming language.

    `text`: Text to validate.
    `language`: Language enum value of language to check `text` against. If `language` is
                `None` (default), try each supported language in turn.

    Return: Language enum value representing programming language `text` belongs to, or
            `None`.

    '''
    result = None

    if language is None:
        for l in Language:
            if validate_source_text_language(text, l):
                result = l

    elif language == Language.C:
        pass # TODO

    elif language == Language.CPP:
        pass # TODO

    elif language == Language.PYTHON:
        try:
            ast.parse(text)
            result = language
        except SyntaxError:
            result = None

    return result


def validate_source_file_language(path, language=None):
    '''Determine whether the contents of the file at `path` is valid code in some
    programming language.

    `path`: Path to file to validate.
    `language`: Language enum value of language to check `text` against. If `language` is
                `None` (default), guess based on file extension.

    Return: Language enum value representing programming language the contents of the file
            at `path` belongs to, or `None`.

    '''
    path = Path(path)

    result = None

    if language is None:
        if path.suffix in ('.c', '.h'):
            # Try C, then try C++.
            result = validate_source_file_language(path, Language.C)
            if not result:
                result = validate_source_file_language(path, Language.CPP)

        elif path.suffix in ('.cpp', '.cc', '.hpp', '.hh'):
            result = validate_source_file_language(path, Language.CPP)

        elif path.suffix == '.py':
            result = validate_source_file_language(path, Language.PYTHON)

    elif language in (Language.C, Language.CPP):
        try:
            index = clang.cindex.Index.create()
            translation = index.parse(
                path,
                args=('--language', language, f'-I{LIBCLANG_HEADER_PATH}')
            )
            # Verify if no parse issues (parse issues are Clang diagnostic category 4).
            if all(
                    diagnostic.category_number != 4
                    for diagnostic in translation.diagnostics
            ):
                result = language

        except clang.cindex.TranslationUniteLoadError:
            result = None

    elif language == Language.PYTHON:
        with open(path) as source_file:
            result = validate_source_text_language(source_file.read(), language)

    return result


def is_comment_code(comment, language):
    '''Is `comment` just commented out code?

    This function does not simply check whether the comment is syntactically valid
    code. For comments that are syntactically valid code, it also tries to determine
    whether the comment is natural language that also happens to be syntactically valid
    code. To be considered natural language, a syntactically valid code snippet must...

    - ...*not* contain *any* of the following characters: '(', ')', '[', ']', '=', '.'
    - ...*not* contain the text "return"

    '''
    if language in (Language.C, Language.CPP):
        return False # TODO commented-out C/C++ code

    elif language == Language.PYTHON:
        trimmed_comment = trim_comment_as_code(comment, language)
        # Check if comment is valid code and contains parentheses, brackets, equals signs,
        # periods, or the word 'return'.
        return (
            validate_source_text_language(trimmed_comment, Language.PYTHON)
            and (
                set('()[]=.').intersection(set(trimmed_comment))
                or 'return' in trimmed_comment
            )
        )


def _get_comment_tokens_from_source_file(path, language):
    '''Retrieve all comment tokens from a file.

    `path`: Path to file to extract comments from.
    `language`: Programming language of the file at `path`.

    Return: List of token objects. The structure of these objects will depend on the
            programming language that was parsed.

    '''
    if language in (Language.C, Language.CPP):
        index = clang.cindex.Index.create()
        translation = index.parse(
            path,
            args=('--language', language, f'-I{LIBCLANG_HEADER_PATH}'),
        )
        tokens = [
            token for token in translation.cursor.get_tokens()
            if token.kind == clang.cindex.TokenKind.COMMENT
        ]

    elif language == Language.PYTHON:
        with tokenize.open(path) as source_file:
            tokens = [
                token for token in tokenize.generate_tokens(source_file.readline)
                if token.type == tokenize.COMMENT
            ]

    return tokens


def _get_token_span(token, language):
    '''Get start and end positions of a token.

    `token`: Token object returned by `_get_commment_tokens_from_source_file()`.
    `language`: Langauge enum value of the programming language the token came from.

    Return: Pair of _TextPos named tuples, the first of which is represents the start of
            the span, the second of which represents the end of the span.

    '''
    if language in (Language.C, Language.CPP):
        start = _TextPos(token.extent.start.line, token.extent.start.column)
        end = _TextPos(token.extent.end.line, token.extent.end.column)

    elif language == Language.PYTHON:
        start = _TextPos(token.start[0], token.start[1])
        end = _TextPos(token.end[0], token.end[1])

    else:
        raise ValueError(f"`language` must be one of {{{','.join(Language)}}}, not {language}")

    return start, end


def _get_token_text(token, language):
    '''Get the text associated with a token object.

    `token`: Token object returned by `_get_commment_tokens_from_source_file()`.
    `language`: Langauge enum value of the programming language the token came from.

    Return: String containing token text.

    '''
    if language in (Language.C, Language.CPP):
        try:
            text = token.spelling
        except UnicodeDecodeError:
            raise TokenizationError()

    elif language == Language.PYTHON:
        text = token.string

    else:
        raise ValueError(f"`language` must be one of {{{','.join(Language)}}}, not {language}")

    return text


def _create_note_element(
        text,
        authors,
        revisions,
        note_type,
        repo,
        path=None,
        first_line=None,
        last_line=None,
        language=None,
):
    '''Create an XML subelement representing a source annotation.

    `parent`: Parent XML element. Should be the root <notes> element of a corpus file.
    `text`: Text of the annotation.
    `authors`: List of authors of the annotation.
    `revisions`: List of revisions in which the annotation was made.
    `note_type`: NoteType enum value representing annotation type.
    `repo`: Either a RepoManager object representing the repository the annotation came
            from, or simply the name of the repository the annotation came from.
    `path`: Path to the file the annotation came from. Only relevant for comments.
    `first_line`: First line of the file on which the annotation appears. Only relevant
                  for comments.
    `last_line`: Last line of the file on which the annotation appears. Only relevant for
                 comments.
    `language`: Language enum value representing the programming language this annotation
                annotated.

    Return: Corpus-ready ElementTree.SubElement object.

    '''
    if note_type == NoteType.COMMENT and language is None:
        raise ValueError(f"`language` cannot be `None` when `note_type` is `{NoteType.COMMENT}`")

    if note_type == NoteType.COMMENT and (first_line is None or last_line is None):
        raise ValueError(f"first_line and last_line cannot be `None` when `note_type` is `{NoteType.COMMENT}`")

    note_elt = ElementTree.Element('note')

    # XML element for repo.
    repo_elt = ElementTree.SubElement(note_elt, 'repo')
    repo_elt.text = str(repo)

    # XML element(s) for author(s).
    for author in authors:
        author_elt = ElementTree.SubElement(note_elt, 'author')
        author_elt.text = author

    # XML element(s) for revision(s).
    for rev in revisions:
        rev_elt = ElementTree.SubElement(note_elt, 'revision')
        rev_elt.text = rev

    # XML element for note type.
    note_type_elt = ElementTree.SubElement(note_elt, 'note-type')
    note_type_elt.text = str(note_type)

    # XML element for file.
    if path is not None:
        file_elt = ElementTree.SubElement(note_elt, 'file')
        file_elt.text = str(path)

    # XML elements for first line and last line.
    if first_line is not None:
        first_line_elt = ElementTree.SubElement(note_elt, 'first-line')
        first_line_elt.text = str(first_line)

    if last_line is not None:
        last_line_elt = ElementTree.SubElement(note_elt, 'last-line')
        last_line_elt.text = str(last_line)

    # XML element for language.
    if language is not None:
        language_elt = ElementTree.SubElement(note_elt, 'language')
        language_elt.text = language

    # XML element for raw text.
    raw_elt = ElementTree.SubElement(note_elt, 'raw')
    raw_elt.text = text

    # Tokenize text. Strip delimiters from comments.
    if note_type == NoteType.COMMENT:
        stripped_text = strip_comment_delimiters(text, language)
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


def _accumulate_comments_from_source_file(path, repo, language, write_build_notes=False):
    '''Get all comments from a programming source file.

    `path`: Path to file.
    `repo`: RepoManager object associated with source file's repository.
    `language`: Programming language associated with file.

    Return: List of dicts where each dict corresponds to a single comment, with the
            following keys:
            - 'comment': Text of the comment.
            - 'authors': List of anonymized author IDs, retrieved from repository blame
                         data.
            - 'revs': List of revision IDs, retrieved from repository blame data.
            - 'path': Path to file. Same as `path` argument.
            - 'first-line': First line the comment appears on in the file.
            - 'last-line': Last line the comment appears on in the file.

    '''
    comment = ""
    authors = set()
    revs = set()
    first_line = 0
    last_line = 0
    last_line_had_comment = False
    first_comment_found = False
    comment_elements = []

    blame_index = BlameIndex(repo, 'HEAD', path.relative_to(repo.dir))
    last_line_with_comment = 0 # tokenize functions index lines from 1

    for token in _get_comment_tokens_from_source_file(path, language):
        token_start, token_end = _get_token_span(token, language)

        if last_line_with_comment == token_start.line-1:
            # Continuation of previous comment.
            comment += f"{_get_token_text(token, language)}\n"
            for blame in blame_index[token_start.line:token_end.line+1]:
                authors.add(anonymize_id(blame.commit.author.name))
                revs.add(blame.commit.name_rev[:7])
            last_line = token_end.line

        else:
            # New comment.
            if last_line_with_comment != 0:
                # Accumulate previous comment.
                if write_build_notes and is_comment_code(comment, language):
                    with open(BUILDNOTES_EXCLUDED_CODE_PATH, 'a') as f:
                        f.write(comment)
                        f.write(f"{'<>'*32}\n")
                else:
                    if (
                            write_build_notes
                            and validate_source_text_language(trim_comment_as_code(comment, language))
                    ):
                        with open(BUILDNOTES_INCLUDED_CODE_PATH, 'a') as f:
                            f.write(comment)
                            f.write(f"{'<>'*32}\n")

                    comment_elements.append(_create_note_element(
                        comment,
                        authors,
                        revs,
                        NoteType.COMMENT,
                        repo,
                        path,
                        first_line,
                        last_line,
                        language,
                    ))

            comment = f"{_get_token_text(token, language)}\n"
            authors = set(
                anonymize_id(blame.commit.author.name)
                for blame in blame_index[token_start.line:token_end.line+1]
            )
            revs = set(
                blame.commit.name_rev[:7]
                for blame in blame_index[token_start.line:token_end.line+1]
            )
            first_line = token_start.line

        last_line_with_comment = token_end.line

    return comment_elements


def _repo_path_comment_consumer(
        repo,
        paths,
        comment_element_lists_by_file,
        write_build_notes=False,
):
    '''Extract comments from all paths in a repo.

    Intended to be run in one of several threads.

    `repo`: RepoManager object.
    `paths`: Thread-safe container (e.g. deque) of all file paths in the repo. Must be
             enumerated (i.e. have the structure created by the `enumerate()` built-in).
    `comment_element_lists_by_file`: Output object. Must be a thread-safe container
                                     (e.g. deque) the same length as `paths`. The initial
                                     contents of the container are irrelevant. After
                                     execution of the function, will be a list of lists,
                                     each list containing `ElementTree.Element` objects
                                     for the XML representation of the comments extracted
                                     from a single source file.

    '''
    while paths:
        i, path = paths.pop()

        logging.debug(f"thread={threading.get_ident()} index={i} path={path}")

        language = validate_source_file_language(path)

        if language:
            try:
                comment_elements = _accumulate_comments_from_source_file(
                    path,
                    repo,
                    language,
                    write_build_notes=write_build_notes,
                )
                comment_element_lists_by_file[i] = comment_elements

            # Don't extract comments that we cannot read.
            except TokenizationError:
                comment_element_lists_by_file[i] = []

        else:
            comment_element_lists_by_file[i] = []


def _create_repo_comments_xml_tree(repo, write_build_notes=False):
    '''Extract comments from a repository and build an XML tree to contain them.

    `repo`: RepoManager object.

    Return: Corpus-ready ElementTree.ElementTree object

    '''
    paths = deque(enumerate(repo.dir.glob('**/*')))
    comment_element_lists_by_file = deque(len(paths) * [None])
    threads = [
        Thread(
            target=_repo_path_comment_consumer,
            args=[repo, paths, comment_element_lists_by_file],
            kwargs={'write_build_notes': write_build_notes},
        ) for i in range(mp.cpu_count()) # TODO use arg
    ]
    for t in threads:
        t.start()

    while any(t.is_alive() for t in threads): pass

    root = ElementTree.Element('notes')
    for element in itr.chain(*comment_element_lists_by_file):
        if element is not None:
            root.append(element)

    return ElementTree.ElementTree(root)


def extract_data(note_types=(), write_build_notes=False):
    '''Extract data from downloaded repos.

    `note_types`: Iterable of NoteType values. Only notes of this type will be extracted.

    '''

    logging.info("Extracting data...")

    CORPUSDIR_PATH.mkdir(exist_ok=True)

    if write_build_notes:
        # Remove build_notes directory (if it exists).
        if (
                NoteType.COMMENT in note_types
                and BUILDNOTESDIR_PATH.is_dir()
        ):
            shutil.rmtree(BUILDNOTESDIR_PATH)

        BUILDNOTESDIR_PATH.mkdir()

    for repo in RepoManager.get_repolist():
        logging.info(f" {repo.name}")

        # Extract changelogs.
        changelogs_path = CORPUSDIR_PATH / Path(f'{NoteType.CHANGELOG}.{repo.name}.xml')
        if NoteType.CHANGELOG in note_types:
            logging.debug(f"  {NoteType.CHANGELOG}")
            changelogs_root = ElementTree.Element('notes')
            for commit in repo.git.iter_commits():
                if commit.message:
                    changelogs_root.append(_create_note_element(
                        normalize_string(commit.message),
                        [anonymize_id(commit.author.name)],
                        [commit.name_rev[:7]],
                        NoteType.CHANGELOG,
                        repo,
                    ))

            changelogs_tree = ElementTree.ElementTree(changelogs_root)
            changelogs_tree.write(
                changelogs_path,
                encoding='utf-8',
                xml_declaration=True,
            )

        # Extract comments.
        comments_path = CORPUSDIR_PATH / Path(f'{NoteType.COMMENT}.{repo.name}.xml')
        if NoteType.COMMENT in note_types:
            logging.debug(f"  {NoteType.COMMENT}")
            comments_tree = _create_repo_comments_xml_tree(
                repo,
                write_build_notes=write_build_notes
            )
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
    note_types = tuple(NoteType)

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

    if args.note_types:
        note_types = args.note_types

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
        extract_data(note_types=note_types, write_build_notes=args.build_notes)


if __name__== '__main__': main(sys.argv[1:])

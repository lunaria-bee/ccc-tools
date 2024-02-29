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
from collections import namedtuple
from hashlib import sha256 as anon_hash
from nltk.tag import pos_tag
from nltk.tokenize import sent_tokenize
from nltk.tokenize import word_tokenize
from pathlib import Path
from xml.etree import ElementTree

import ast
import clang.cindex
import itertools as itr
import logging
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
        " Not currently implemented for 'extract' or 'annotate'."
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
    '''TODO'''
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
    '''TODO

    If `language` is `None` (default), try each supported language in turn.

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
    '''TODO

    If `language` is `None` (default), guess based on file extension.

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
    '''TODO'''
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
    '''TODO'''
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
    '''TODO'''
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


def _accumulate_comments_from_source_file(path, repo, language):
    '''TODO'''
    comment = ""
    authors = set()
    revs = set()
    first_line = 0
    last_line = 0
    last_line_had_comment = False
    first_comment_found = False
    comment_dicts = []

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
                if is_comment_code(comment, language):
                    with open(BUILDNOTES_EXCLUDED_CODE_PATH, 'a') as f:
                        f.write(comment)
                        f.write(f"{'<>'*32}\n")
                else:
                    if validate_source_text_language(trim_comment_as_code(comment, language)):
                        with open(BUILDNOTES_INCLUDED_CODE_PATH, 'a') as f:
                            f.write(comment)
                            f.write(f"{'<>'*32}\n")

                    comment_dicts.append({
                        'comment': comment,
                        'authors': authors,
                        'revs': revs,
                        'path': path,
                        'first-line': first_line,
                        'last-line': last_line,
                    })

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

    return comment_dicts


def _create_note_subelement(
        parent,
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
    '''TODO'''
    if note_type == NoteType.COMMENT and language is None:
        raise ValueError(f"`language` cannot be `None` when `note_type` is `{NoteType.COMMENT}`")

    if note_type == NoteType.COMMENT and (first_line is None or last_line is None):
        raise ValueError(f"first_line and last_line cannot be `None` when `note_type` is `{NoteType.COMMENT}`")

    note_elt = ElementTree.SubElement(
        parent,
        'note',
    )

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


def _create_repo_comments_xml_tree(repo):
    '''TODO'''
    root = ElementTree.Element('notes')
    for source_path in repo.dir.glob('**/*'):
        language = validate_source_file_language(source_path)

        if language:
            try:
                comment_dicts = _accumulate_comments_from_source_file(source_path, repo, language)
                for d in comment_dicts:
                    _create_note_subelement(
                        root,
                        d['comment'],
                        d['authors'],
                        d['revs'],
                        NoteType.COMMENT,
                        repo,
                        d['path'],
                        d['first-line'],
                        d['last-line'],
                        language,
                    )

            # Don't extract comments for file that we cannot read.
            except TokenizationError:
                continue

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
                        [commit.name_rev[:7]],
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
        redo_note_types = note_types
    else:
        redo_note_types = tuple()

    extract_data(force_reextract=redo_note_types)


if __name__== '__main__': main(sys.argv[1:])

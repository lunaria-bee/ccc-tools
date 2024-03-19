'''NLTK reader for Code Comment Corpus.'''


from defines import NoteType
from repo import RepoManager

from nltk.corpus.reader.api import CategorizedCorpusReader
from nltk.corpus.reader.xmldocs import XMLCorpusReader
from timeit import timeit
from xml.etree import ElementTree


def get_fileid_components(fileid):
    '''Split a corpus fileid into its semantic components.

    Return: Python dict of:
            - 'note-type': NoteType enum value of what type of annotations the file
                           contains.
            - 'repo': Name of the repository the file's data came from, as a string.
            - 'extension': Extension of the file. Will generally be "xml".    

    '''
    components = fileid.split('.')
    return {
        'note-type': NoteType(components[0]),
        'repo': components[1],
        'extension': components[2],
    }


class CccReader(CategorizedCorpusReader, XMLCorpusReader):
    '''Reader class for Code Comment Corpus.'''

    def __init__(self):
        root = 'corpus'
        fileids = r'.*?\..*?\.xml'
        XMLCorpusReader.__init__(self, root, fileids)
        CategorizedCorpusReader.__init__(self, kwargs={'cat_pattern': r'(.*?)\..*?\.xml'})

    def _filter_fileids(self, fileids=None, categories=None, repos=None):
        '''Return fileids that match all provided criteria.

        If more than one of parameter is set, only return fileids that satisfy all
        provided criteria.

        fileids: List of fileids.
        categories: List of note categories (see defines.NoteType).
        repos: List of repositories. Each element may be either the repository name as a
               string, or a RepoManager object. The list may contain a mixture of both.

        Return: List of fileids that match all provided criteria.

        '''
        computed_fileids = self.fileids(categories, repos)
        if fileids is None:
            return computed_fileids
        else:
            return [fileid for fileid in fileids if fileid in computed_fileids]

    def fileids(self, categories=None, repos=None):
        '''Return a list of file identifiers for the files that make up this corpus.

        May optionally filter to a subcorpus using the categories and repos arguments. If
        more than one of these parameters is set, only select fileids that satisfy all
        provided criteria.

        categories: List of note categories (see defines.NoteType).
        repos: List of repositories. Each element may be either the repository name as a
               string, or a RepoManager object. The list may contain a mixture of both.

        '''
        fileids = CategorizedCorpusReader.fileids(self, categories)

        if repos is not None:
            repos = [repo.name if isinstance(repo, RepoManager) else repo for repo in repos]
            fileids = [fileid for fileid in fileids
                       if get_fileid_components(fileid)['repo'] in repos]

        return fileids

    def repos(self):
        '''Get list of repositories corpus data was extracted from.'''
        return set(
            get_fileid_components(fileid)['repo']
            for fileid in self.fileids()
        )

    def xml(self, fileids=None, categories=None, repos=None):
        '''Get Python representation of corpus XML.

        Concatenate all XML from all corpus files, or those selected by the fileids,
        categories, and repos arguments. If more than one of these parameters is set, only select
        fileids that satisfy all provided criteria.

        fileids: List of fileids.
        categories: List of note categories (see defines.NoteType).
        repos: List of repositories. Each element may be either the repository name as a
               string, or a RepoManager object. The list may contain a mixture of both.

        Return: xml.etree.ElementTree.Element tree representing the corpus.

        '''
        fileids = self._filter_fileids(fileids, categories, repos)

        xml_root = ElementTree.Element('notes')
        for fileid in fileids:
            file_notes = XMLCorpusReader.xml(self, fileid)
            for note in file_notes:
                xml_root.append(note)

        return xml_root

    def words(self, fileids=None, categories=None, repos=None):
        '''Get list of all tokens in corpus.

        May optionally filter to a subcorpus using the fileids, categories, and repos
        arguments. If more than one of these parameters is set, only select fileids that
        satisfy all provided criteria.

        fileids: List of fileids.
        categories: List of note categories (see defines.NoteType).
        repos: List of repositories. Each element may be either the repository name as a
               string, or a RepoManager object. The list may contain a mixture of both.

        '''
        # TODO Stip comment delimiters.

        # fileids = self._filter_fileids(fileids, categories, repos)

        # words = []
        # for fileid in fileids:
        #     words.extend(super().words(fileids=[fileid]))

        xml = self.xml(fileids, categories, repos)

        words = []
        for note in xml:
            if note.find('tokens').text:
                words.extend(note.find('tokens').text.split())
            else:
                # Empty comment; just delimiter(s).
                words.append(" ")

        return words

    def sents(self, fileids=None, categories=None, repos=None):
        '''Get a list of tokenized sentences.

        May optionally filter to a subcorpus using the fileids, categories, and repos
        arguments. If more than one of these parameters is set, only select fileids that
        satisfy all provided criteria.

        fileids: List of fileids.
        categories: List of note categories (see defines.NoteType).
        repos: List of repositories. Each element may be either the repository name as a
               string, or a RepoManager object. The list may contain a mixture of both.

        Return: List of sentences, where each element of the return list is itself a list
                of the tokens in that sentence.

        '''
        # TODO Strip comment delimiters.

        xml = self.xml(fileids, categories, repos)

        sents = []
        for note in xml:
            if note.find('tokens').text:
                sents.extend(
                    sent.split(' ')
                    for sent in note.find('tokens').text.split('\n')
                )
            else:
                # Empty comment; just delimiters.
                sents.append([" "])

        return sents

    def pos(self, fileids=None, categories=None, repos=None):
        '''Get pairs of the form (word, part-of-speech tag).

        May optionally filter to a subcorpus using the fileids, categories, and repos
        arguments. If more than one of these parameters is set, only select fileids that
        satisfy all provided criteria.

        `fileids`: List of fileids.
        `categories`: List of note cateogires (see defines.NoteType).
        `repos`: List of repositories. Each element may be either the repository name as a
               string, or a RepoManager object. The list may contain a mixture of both.

        Return: List of tuples, where each tuple is a pair of the form
                (word, part-of-speech tag).

        '''
        xml = self.xml(fileids, categories, repos)

        word_pos_pairs = []
        for note in xml:
            if note.find('tokens').text:
                words = note.find('tokens').text.split()
                pos = note.find('pos').text.split()
                word_pos_pairs.extend(zip(words, pos))

        return word_pos_pairs

    def stats(self):
        '''Print statistics about the size of the corpus and sub-corpora.'''
        repos = self.repos()
        categories = self.categories()

        for repo in repos:
            for cat in categories:
                word_count = len(self.words(repos=[repo], categories=[cat]))
                sent_count = len(self.sents(repos=[repo], categories=[cat]))
                note_count = len(self.xml(repos=[repo], categories=[cat]))

                print(f"{repo} {cat} words: {word_count}")
                print(f"{repo} {cat} sents: {sent_count}")
                print(f"{repo} {cat} notes: {note_count}")
                print()

            word_count = len(self.words(repos=[repo]))
            sent_count = len(self.sents(repos=[repo]))
            note_count = len(self.xml(repos=[repo]))

            print(f"{repo} words: {word_count}")
            print(f"{repo} sents: {sent_count}")
            print(f"{repo} notes: {note_count}")
            print()

        for cat in categories:
            word_count = len(self.words(categories=[cat]))
            sent_count = len(self.sents(categories=[cat]))
            note_count = len(self.xml(categories=[cat]))

            print(f"{cat} words: {word_count}")
            print(f"{cat} sents: {sent_count}")
            print(f"{cat} notes: {note_count}")
            print()

        word_count = len(self.words())
        sent_count = len(self.sents())
        note_count = len(self.xml())

        print(f"words: {word_count}")
        print(f"sents: {sent_count}")
        print(f"notes: {note_count}")

    def performance(self, trials=100):
        '''Print perfomance statistics for CccReader methods.'''
        repos = self.repos()
        categories = self.categories()

        for repo in repos:
            for cat in categories:
                word_time = timeit(
                    "self.words(repos=[repo], categories=[cat])",
                    number=trials,
                    globals=vars(),
                ) / trials
                sent_time = timeit(
                    "self.sents(repos=[repo], categories=[cat])",
                    number=trials,
                    globals=vars(),
                ) / trials
                note_time = timeit(
                    "self.xml(repos=[repo], categories=[cat])",
                    number=trials,
                    globals=vars(),
                ) / trials

                print(f"{repo} {cat} words: {word_time}")
                print(f"{repo} {cat} sents: {sent_time}")
                print(f"{repo} {cat} notes: {note_time}")
                print()

            word_time = timeit(
                "self.words(repos=[repo])",
                number=trials,
                globals=vars(),
            ) / trials
            sent_time = timeit(
                "self.sents(repos=[repo])",
                number=trials,
                globals=vars(),
            ) / trials
            note_time = timeit(
                "self.xml(repos=[repo])",
                number=trials,
                globals=vars(),
            ) / trials

            print(f"{repo} words: {word_time}")
            print(f"{repo} sents: {sent_time}")
            print(f"{repo} notes: {note_time}")
            print()

        for cat in categories:
            word_time = timeit(
                "self.words(categories=[cat])",
                number=trials,
                globals=vars(),
            ) / trials
            sent_time = timeit(
                "self.sents(categories=[cat])",
                number=trials,
                globals=vars(),
            ) / trials
            note_time = timeit(
                "self.xml(categories=[cat])",
                number=trials,
                globals=vars(),
            ) / trials

            print(f"{cat} words: {word_time}")
            print(f"{cat} sents: {sent_time}")
            print(f"{cat} notes: {note_time}")
            print()

        word_time = timeit(
            "self.words()",
            number=trials,
            globals=vars(),
        ) / trials
        sent_time = timeit(
            "self.sents()",
            number=trials,
            globals=vars(),
        ) / trials
        note_time = timeit(
            "self.xml()",
            number=trials,
            globals=vars(),
        ) / trials

        print(f"words: {word_time}")
        print(f"sents: {sent_time}")
        print(f"notes: {note_time}")

    # TODO override paras()

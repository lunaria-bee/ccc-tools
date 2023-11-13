'''TODO'''


from defines import NoteType
from repo import RepoManager

from nltk.corpus.reader.api import CategorizedCorpusReader
from nltk.corpus.reader.xmldocs import XMLCorpusReader
from nltk.tokenize import sent_tokenize
from nltk.tokenize import word_tokenize
from xml.etree import ElementTree

import re


def get_fileid_components(fileid):
    '''TODO'''
    components = fileid.split('.')
    return {
        'note-type': NoteType(components[0]),
        'repo': components[1],
        'extension': components[2],
    }


class CccReader(CategorizedCorpusReader, XMLCorpusReader):
    '''TODO'''

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
            repos = (repo.name if isinstance(repo, RepoManager) else repo for repo in repos)
            fileids = [fileid for fileid in fileids
                       if get_fileid_components(fileid)['repo'] in repos]

        return fileids

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

        fileids = self._filter_fileids(fileids, categories, repos)

        words = []
        for fileid in fileids:
            words.extend(super().words(fileids=[fileid]))

        return words

    # TODO override sents()
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
            # Normalize whitespace.
            if note.text:
                sents.extend(word_tokenize(sent) for sent in sent_tokenize(note.text))

        return sents

    # TODO override paras()

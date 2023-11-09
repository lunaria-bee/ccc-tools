'''TODO'''


from defines import NoteType

from nltk.corpus.reader.api import CategorizedCorpusReader
from nltk.corpus.reader.xmldocs import XMLCorpusReader


class CccReader(CategorizedCorpusReader, XMLCorpusReader):
    '''TODO'''

    def __init__(self):
        root = 'corpus'
        fileids = r'.*?\..*?\.xml'
        XMLCorpusReader.__init__(self, root, fileids)
        CategorizedCorpusReader.__init__(self, kwargs={'cat_pattern': r'(.*?)\..*?\.xml'})

    # TODO override xml()
    # TODO override words()
    # TODO override sents()
    # TODO delete paras()
    # TODO create notes()

"""A Document Converter

To use `lexor` as a module you should explore in detail the packages
provided with `lexor`. These packages contain many other functions
and information which can help you convert your document in the way
you desire.

## core

The core of lexor defines basic objects such as `Document` and
provides the main objects that define the functions provided in this
module.

## command

This module is in charge of providing all the available commands to
lexor.

"""

from sys import stdout
from os.path import realpath, basename, splitext
from .core.lang import load_aux
from .core.parser import Parser
from .core.writer import Writer
from .core.converter import Converter
from .command import error
from .__version__ import get_version

__all__ = ['parse', 'read', 'convert', 'write', 'init', 'load_aux']


def parse(text, lang='xml', style='default'):
    """Parse the text in a given language and return the `Document`
    form and a `Document` log containing the errors encountered
    during parsing. """
    parser = Parser(lang, style)
    parser.parse(text)
    return (parser.document, parser.log)


def read(filename, style="default", lang=None):
    """Read and parse a file. If lang is not specified then the
    language is assummed from the filename extension. Returns the
    `Document` form and a `Document` log containing the errors
    encountered during parsing. """
    if lang is None:
        path = realpath(filename)
        name = basename(path)
        name = splitext(name)
        lang = name[1][1:]
    with open(filename, 'r') as tmpf:
        text = tmpf.read()
    parser = Parser(lang, style)
    parser.parse(text, filename)
    return (parser.document, parser.log)


def convert(doc, lang=None, style="default"):
    """Convert the `Document` doc to another language in a given
    style. If the lang is not specified then the document is
    tranformed to the same language as the document using the default
    style.

    """
    if lang is None:
        lang = doc.owner.lang
    converter = Converter(doc.owner.lang, lang, style)
    converter.convert(doc)
    return (converter.document, converter.log)


def write(doc, filename=None, mode='w'):
    """Write doc to a file. To write to the standard output use the
    default parameters, otherwise provide a file name. If filename is
    provided you have the option of especifying the mode: 'w' or 'a'.

    You may also provide a file you may have opened yourself in
    place of filename so that the writer writes to that file.

    """
    if doc.owner is None:
        style = 'default'
        lang = 'xml'
    else:
        style = doc.owner.style
        lang = doc.owner.lang
    writer = Writer(lang, style)
    if filename:
        writer.write(doc, filename, mode)
    else:
        writer.write(doc, stdout)


def init(**keywords):
    """Every lexor style needs to call the init function. These are
    the valid keywords to initialize a style:

        version: Must be in form (major, minor, micro, alpha/beta/rc/final, #)
        lang
        [to_lang]
        type
        description
        author
        author_email
        [url]
        license
        path: Must be present and set to __file__.

    """
    valid_keys = ['version', 'lang', 'to_lang', 'type', 'description',
                  'author', 'author_email', 'url', 'path', 'license']
    info = dict()
    for key in valid_keys:
        info[key] = None
    for key in keywords.keys():
        if key not in valid_keys:
            error("ERROR: Valid keys for lexor.init are %s" % valid_keys)
        else:
            info[key] = keywords[key]
    info['style'] = splitext(basename(info['path']))[0]
    info['style'] = info['style'].split('-')[0]
    info['ver'] = get_version(info['version'])
    return info

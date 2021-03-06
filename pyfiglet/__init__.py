#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Python FIGlet adaption
"""

from __future__ import print_function, unicode_literals

# import pkg_resources  # This causes issues with Sublime Text's limited standard library.
import importlib        # This should be generally available.
import os
import re
import sys
from optparse import OptionParser
import time

from .version import __version__

__author__ = 'Peter Waller <peter.waller@gmail.com>'
__copyright__ = """
Copyright (C) 2007 Christopher Jones <cjones@gruntle.org>
Tweaks (C) 2011 Peter Waller <peter.waller@gmail.com>
       (C) 2011 Stefano Rivera <stefano@rivera.za.net>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
"""


DEFAULT_FONT = 'standard'


#### Replacements for pkg_resources  ####

def get_pkg_dir(pkg):
    try:
        if pkg in sys.modules:
            mod = sys.modules[pkg]
        else:
            # I don't think there is a big penalty of importing multiple times...?
            mod = importlib.import_module(pkg)
    except ImportError:
        return False
    return os.path.dirname(os.path.abspath(mod.__file__))

def get_res_path(pkg, res):
    pkgdir = get_pkg_dir(pkg)
    return os.path.join(pkgdir, res)

def resource_exists(pkg, resource):
    path = get_res_path(pkg, resource)
    return os.path.isfile(path)

def resource_string(pkg, resource):
    path = get_res_path(pkg, resource)
    with open(path) as fd:
        res_str = fd.read()
    return res_str

def resource_stream(pkg, resource):
    path = get_res_path(pkg, resource)
    fd = open(path)
    return fd

def resource_listdir(pkg, resource):
    path = get_res_path(pkg, resource)
    #return os.path.listdir(path)
    return os.listdir(path)


### Utility functions ###

def figlet_format(text, font=DEFAULT_FONT, **kwargs):
    fig = Figlet(font, **kwargs)
    return fig.renderText(text)


def print_figlet(text, font=DEFAULT_FONT, **kwargs):
    print(figlet_format(text, font, **kwargs))


### Error classes ###

class FigletError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return self.error


class FontNotFound(FigletError):
    """
    Raised when a font can't be located
    """


class FontError(FigletError):
    """
    Raised when there is a problem parsing a font file
    """


class FigletFont(object):
    """
    This class represents the currently loaded font, including
    meta-data about how it should be displayed by default
    """

    reMagicNumber = re.compile(r'^[tf]lf2.')
    reEndMarker = re.compile(r'(.)\s*$')

    def __init__(self, font=DEFAULT_FONT, **kwargs):
        self.font = font

        self.comment = ''
        self.chars = {}
        self.width = {}
        self.data = self.preloadFont(font)
        self.loadFont()
        if 'smushMode' in kwargs:
            # Override the smushMode inferred by loadFont():
            self.smushMode = kwargs['smushMode']

    @classmethod
    def preloadFont(cls, font):
        """
        Load font data if exist
        """
        for extension in ('tlf', 'flf'):
            fn = '%s.%s' % (font, extension)
            if resource_exists('pyfiglet.fonts', fn):
                # https://pythonhosted.org/setuptools/pkg_resources.html
                # This loads pyfiglet.fonts/<font>.tlf file into data variable.
                data = resource_string('pyfiglet.fonts', fn)
                try:
                    data = data.decode('UTF-8', 'replace')
                except AttributeError:
                    # python3 has no decode on strings; and strings are already UTF-8 by default.
                    # Alternatively, use codecs.open to read the string.
                    pass
                return data
        else:
            raise FontNotFound(font)

    @classmethod
    def isValidFont(cls, font):
        if not font.endswith(('.flf', '.tlf')):
            return False
        with resource_stream('pyfiglet.fonts', font) as f:
            header = f.readline().decode('UTF-8', 'replace')
        return cls.reMagicNumber.search(header)

    @classmethod
    def getFonts(cls):
        return [font.rsplit('.', 2)[0] for font
                #in pkg_resources.resource_listdir('pyfiglet', 'fonts')
                in resource_listdir('pyfiglet', 'fonts')
                if cls.isValidFont(font)]

    @classmethod
    def infoFont(cls, font, short=False):
        """
        Get informations of font
        """
        data = FigletFont.preloadFont(font)
        infos = []
        reStartMarker = re.compile(r"""
            ^(FONT|COMMENT|FONTNAME_REGISTRY|FAMILY_NAME|FOUNDRY|WEIGHT_NAME|
              SETWIDTH_NAME|SLANT|ADD_STYLE_NAME|PIXEL_SIZE|POINT_SIZE|
              RESOLUTION_X|RESOLUTION_Y|SPACING|AVERAGE_WIDTH|COMMENT|
              FONT_DESCENT|FONT_ASCENT|CAP_HEIGHT|X_HEIGHT|FACE_NAME|FULL_NAME|
              COPYRIGHT|_DEC_|DEFAULT_CHAR|NOTICE|RELATIVE_).*""", re.VERBOSE)
        reEndMarker = re.compile(r'^.*[@#$]$')
        for line in data.splitlines()[0:100]:
            if (cls.reMagicNumber.search(line) is None
                    and reStartMarker.search(line) is None
                    and reEndMarker.search(line) is None):
                infos.append(line)
        return '\n'.join(infos) if not short else infos[0]

    def loadFont(self):
        """
        Parse loaded font data for the rendering engine to consume
        """
        try:
            # Parse first line of file, the header
            data = self.data.splitlines()

            header = data.pop(0)
            if self.reMagicNumber.search(header) is None:
                raise FontError('%s is not a valid figlet font' % self.font)

            header = self.reMagicNumber.sub('', header)
            header = header.split()

            if len(header) < 6:
                raise FontError('malformed header for %s' % self.font)

            hardBlank = header[0]
            height, baseLine, maxLength, oldLayout, commentLines = map(
                int, header[1:6])
            printDirection = fullLayout = None

            # these are all optional for backwards compat
            if len(header) > 6:
                printDirection = int(header[6])
            if len(header) > 7:
                fullLayout = int(header[7])

            # if the new layout style isn't available,
            # convert old layout style. backwards compatability
            if fullLayout is None:
                if oldLayout == 0:
                    fullLayout = 64
                elif oldLayout < 0:
                    fullLayout = 0
                else:
                    fullLayout = (oldLayout & 31) | 128

            # Some header information is stored for later, the rendering
            # engine needs to know this stuff.
            self.height = height
            self.hardBlank = hardBlank
            self.printDirection = printDirection
            self.smushMode = fullLayout

            # Strip out comment lines
            for i in range(0, commentLines):
                self.comment += data.pop(0)

            def __char(data):
                """
                Function loads one character in the internal array from font
                file content
                """
                end = None
                width = 0
                chars = []
                for j in range(0, height):
                    line = data.pop(0)
                    if end is None:
                        end = self.reEndMarker.search(line).group(1)
                        end = re.compile(re.escape(end) + r'{1,2}$')

                    line = end.sub('', line)

                    if len(line) > width:
                        width = len(line)
                    chars.append(line)
                return width, chars

            # Load ASCII standard character set (32 - 127)
            for i in range(32, 127):
                width, letter = __char(data)
                if ''.join(letter) != '':
                    self.chars[i] = letter
                    self.width[i] = width

            # Load ASCII extended character set
            while data:
                line = data.pop(0).strip()
                i = line.split(' ', 1)[0]
                if (i == ''):
                    continue
                hex_match = re.search('^0x', i, re.IGNORECASE)
                if hex_match is not None:
                    i = int(i, 16)
                    width, letter = __char(data)
                    if ''.join(letter) != '':
                        self.chars[i] = letter
                        self.width[i] = width

        except Exception as e:
            raise FontError('problem parsing %s font: %s' % (self.font, e))

    def __str__(self):
        return '<FigletFont object: %s>' % self.font


unicode_string = type(''.encode('ascii').decode('ascii'))


class FigletString(unicode_string):
    """
    Rendered figlet font
    """

    # translation map for reversing ascii art / -> \, etc.
    __reverse_map__ = (
        '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
        '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
        ' !"#$%&\')(*+,-.\\'
        '0123456789:;>=<?'
        '@ABCDEFGHIJKLMNO'
        'PQRSTUVWXYZ]/[^_'
        '`abcdefghijklmno'
        'pqrstuvwxyz}|{~\x7f'
        '\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f'
        '\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'
        '\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf'
        '\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf'
        '\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf'
        '\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf'
        '\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef'
        '\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff')

    # translation map for flipping ascii art ^ -> v, etc.
    __flip_map__ = (
        '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
        '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
        ' !"#$%&\'()*+,-.\\'
        '0123456789:;<=>?'
        '@VBCDEFGHIJKLWNO'
        'bQbSTUAMXYZ[/]v-'
        '`aPcdefghijklwno'
        'pqrstu^mxyz{|}~\x7f'
        '\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f'
        '\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'
        '\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf'
        '\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf'
        '\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf'
        '\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf'
        '\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef'
        '\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff')

    def reverse(self):
        out = []
        for row in self.splitlines():
            out.append(row.translate(self.__reverse_map__)[::-1])

        return self.newFromList(out)

    def flip(self):
        out = []
        for row in self.splitlines()[::-1]:
            out.append(row.translate(self.__flip_map__))

        return self.newFromList(out)

    def newFromList(self, list):
        return FigletString('\n'.join(list) + '\n')


class FigletRenderingEngine(object):
    """
    This class handles the rendering of a FigletFont,
    including smushing/kerning/justification/direction
    """

    def __init__(self, base=None):
        self.base = base

        # constants.. lifted from figlet222
        self.SM_EQUAL = 1    # smush equal chars (not hardblanks)
        self.SM_LOWLINE = 2    # smush _ with any char in hierarchy
        self.SM_HIERARCHY = 4    # hierarchy: |, /\, [], {}, (), <>
        self.SM_PAIR = 8    # hierarchy: [ + ] -> |, { + } -> |, ( + ) -> |
        self.SM_BIGX = 16    # / + \ -> X, > + < -> X
        self.SM_HARDBLANK = 32    # hardblank + hardblank -> hardblank
        self.SM_KERN = 64
        self.SM_SMUSH = 128

    def smushChars(self, left='', right=''):
        """
        Given 2 characters which represent the edges rendered figlet
        fonts where they would touch, see if they can be smushed together.
        Returns None if this cannot or should not be done.
        """
        if left.isspace() is True:
            return right
        if right.isspace() is True:
            return left

        # Disallows overlapping if previous or current char has a width of 1 or
        # zero
        if (self.prevCharWidth < 2) or (self.curCharWidth < 2):
            return

        # kerning only
        if (self.base.Font.smushMode & self.SM_SMUSH) == 0:
            return

        # smushing by universal overlapping
        if (self.base.Font.smushMode & 63) == 0:
            # Ensure preference to visiable characters.
            if left == self.base.Font.hardBlank:
                return right
            if right == self.base.Font.hardBlank:
                return left

            # Ensures that the dominant (foreground)
            # fig-character for overlapping is the latter in the
            # user's text, not necessarily the rightmost character.
            if self.base.direction == 'right-to-left':
                return left
            else:
                return right

        if self.base.Font.smushMode & self.SM_HARDBLANK:
            if (left == self.base.Font.hardBlank
                    and right == self.base.Font.hardBlank):
                return left

        if (left == self.base.Font.hardBlank
                or right == self.base.Font.hardBlank):
            return

        if self.base.Font.smushMode & self.SM_EQUAL:
            if left == right:
                return left

        smushes = ()

        if self.base.Font.smushMode & self.SM_LOWLINE:
            smushes += (('_', r'|/\[]{}()<>'),)

        if self.base.Font.smushMode & self.SM_HIERARCHY:
            smushes += (
                ('|', r'|/\[]{}()<>'),
                (r'\/', '[]{}()<>'),
                ('[]', '{}()<>'),
                ('{}', '()<>'),
                ('()', '<>'),
            )

        for a, b in smushes:
            if left in a and right in b:
                return right
            if right in a and left in b:
                return left

        if self.base.Font.smushMode & self.SM_PAIR:
            for pair in [left+right, right+left]:
                if pair in ['[]', '{}', '()']:
                    return '|'

        if self.base.Font.smushMode & self.SM_BIGX:
            if (left == '/') and (right == '\\'):
                return '|'
            if (right == '/') and (left == '\\'):
                return 'Y'
            if (left == '>') and (right == '<'):
                return 'X'
        return

    def smushAmount(self, left=None, right=None, buffer=[], curChar=[]):
        """
        Calculate the amount of smushing we can do between this char and the
        last If this is the first char it will throw a series of exceptions
        which are caught and cause appropriate values to be set for later.

        This differs from C figlet which will just get bogus values from
        memory and then discard them after.
        """
        if (self.base.Font.smushMode & (self.SM_SMUSH | self.SM_KERN)) == 0:
            return 0

        maxSmush = self.curCharWidth
        for row in range(0, self.base.Font.height):
            lineLeft = buffer[row]
            lineRight = curChar[row]
            if self.base.direction == 'right-to-left':
                lineLeft, lineRight = lineRight, lineLeft

            linebd = len(lineLeft.rstrip()) - 1
            if linebd < 0:
                linebd = 0

            if linebd < len(lineLeft):
                ch1 = lineLeft[linebd]
            else:
                linebd = 0
                ch1 = ''

            charbd = len(lineRight) - len(lineRight.lstrip())
            if charbd < len(lineRight):
                ch2 = lineRight[charbd]
            else:
                charbd = len(lineRight)
                ch2 = ''

            amt = charbd + len(lineLeft) - 1 - linebd

            if ch1 == '' or ch1 == ' ':
                amt += 1
            elif (ch2 != ''
                    and self.smushChars(left=ch1, right=ch2) is not None):
                amt += 1

            if amt < maxSmush:
                maxSmush = amt

        return maxSmush

    def render(self, text):
        """
        Render an ASCII text string in figlet
        """
        self.curCharWidth = self.prevCharWidth = 0
        buffer = ['' for i in range(self.base.Font.height)]

        for c in map(ord, list(text)):
            if c not in self.base.Font.chars:
                continue
            curChar = self.base.Font.chars[c]
            self.curCharWidth = self.base.Font.width[c]
            maxSmush = self.smushAmount(buffer=buffer, curChar=curChar)

            # Add a character to the buffer and do smushing/kerning
            for row in range(0, self.base.Font.height):
                addLeft = buffer[row]
                addRight = curChar[row]

                if self.base.direction == 'right-to-left':
                    addLeft, addRight = addRight, addLeft

                for i in range(0, maxSmush):

                    idx = len(addLeft) - maxSmush + i
                    if idx >= 0 and idx < len(addLeft):
                        left = addLeft[idx]
                    else:
                        left = ''

                    right = addRight[i]

                    smushed = self.smushChars(left=left, right=right)

                    l = list(addLeft)
                    idx = len(l)-maxSmush+i
                    if idx >= 0 and idx < len(l):
                        l[idx] = smushed
                        addLeft = ''.join(l)

                buffer[row] = addLeft + addRight[maxSmush:]

            self.prevCharWidth = self.curCharWidth

        # Justify text. This does not use str.rjust/str.center
        # specifically because the output would not match FIGlet
        if self.base.justify == 'right':
            for row in range(0, self.base.Font.height):
                buffer[row] = (
                    ' ' * (self.base.width - len(buffer[row]) - 1)
                ) + buffer[row]

        elif self.base.justify == 'center':
            for row in range(0, self.base.Font.height):
                buffer[row] = (
                    ' ' * int((self.base.width - len(buffer[row])) / 2)
                ) + buffer[row]

        # return rendered ASCII with hardblanks replaced
        buffer = '\n'.join(buffer) + '\n'
        buffer = buffer.replace(self.base.Font.hardBlank, ' ')

        return FigletString(buffer)


class Figlet(object):
    """
    Main figlet class.
    """

    def __init__(self, font=DEFAULT_FONT, direction='auto', justify='auto',
                 width=80, fontkwargs=None):
        if fontkwargs is None:
            fontkwargs = {}
        self.font = font    # font name (string)
        self.Font = None    # Actual Font object, set by setFont()
        self._direction = direction
        self._justify = justify
        self.width = width
        self.setFont(**fontkwargs)
        self.engine = FigletRenderingEngine(base=self)

    def setFont(self, **kwargs):
        if 'font' in kwargs:
            self.font = kwargs.pop('font')

        self.Font = FigletFont(font=self.font, **kwargs)

    def getDirection(self):
        if self._direction == 'auto':
            direction = self.Font.printDirection
            if direction == 0:
                return 'left-to-right'
            elif direction == 1:
                return 'right-to-left'
            else:
                return 'left-to-right'

        else:
            return self._direction

    direction = property(getDirection)

    def getJustify(self):
        if self._justify == 'auto':
            if self.direction == 'left-to-right':
                return 'left'
            elif self.direction == 'right-to-left':
                return 'right'

        else:
            return self._justify

    justify = property(getJustify)

    def renderText(self, text):
        # wrapper method to engine
        return self.engine.render(text)

    def getFonts(self):
        return self.Font.getFonts()

    def renderAnimate(self, text):
        """
        Devuelve una lista de textos con cada "frame" de la animación.
        """
        full_frame = self.renderText(text)
        len_texto = len(full_frame.split("\n")[0])
        res = []
        p = 0   # principio del slice.
        f = 0   # fin del slice
        rows, columns = map(int, os.popen('stty size', 'r').read().split()) # FIXME: Size of console. Only Linux, I think.
        lineas = full_frame.split("\n")
        for nframe in range(len_texto-1)*2:
            frame = "\n" * ((rows - len(lineas)) / 2)
            for linea in lineas:
                frame += linea[p:f] + "\n"
            res.append(frame)
            f += 1
            if f > columns:
                p += 1
        return res

    def animate(self, text, fps = 12):
        """
        Escribe y borra sucesivamente cada "frame" del texto. Un frame es un
        "slice" del texto completo desde el principio hasta el final añadiendo
        y después quitando una columna de cada línea.
        """
        for frame in self.renderAnimate(text):
            print(frame)
            time.sleep(1.0 / fps)
            os.system("clear")  # FIXME: Solo sistemas UNIX
        exit(0)


def main():
    parser = OptionParser(version=__version__,
                          usage='%prog [options] [text..]')
    parser.add_option('-f', '--font', default=DEFAULT_FONT,
                      help='font to render with (default: %default)',
                      metavar='FONT')
    parser.add_option('-D', '--direction', type='choice',
                      choices=('auto', 'left-to-right', 'right-to-left'),
                      default='auto', metavar='DIRECTION',
                      help='set direction text will be formatted in '
                           '(default: %default)')
    parser.add_option('-j', '--justify', type='choice',
                      choices=('auto', 'left', 'center', 'right'),
                      default='auto', metavar='SIDE',
                      help='set justification, defaults to print direction')
    parser.add_option('-w', '--width', type='int', default=80, metavar='COLS',
                      help='set terminal width for wrapping/justification '
                           '(default: %default)')
    parser.add_option('-r', '--reverse', action='store_true', default=False,
                      help='shows mirror image of output text')
    parser.add_option('-F', '--flip', action='store_true', default=False,
                      help='flips rendered output text over')
    parser.add_option('-l', '--list_fonts', action='store_true', default=False,
                      help='show installed fonts list')
    parser.add_option('-i', '--info_font', action='store_true', default=False,
                      help='show font\'s information, use with -f FONT')
    parser.add_option('-s', '--smushmode', type='int',
                      help='Set how much the text is smushed (forced together). Provided as binary options (power of 2 integers, see manual). Default is 128 (a lot of smushing).')
    parser.add_option('-a', '--animate', action='store_true', default=False,
                      help='Animate text across the screen cleaning and drawing slices of it. Incompatible with flip and reverse.')
    opts, args = parser.parse_args()

    if opts.list_fonts:
        print('\n'.join(sorted(FigletFont.getFonts())))
        exit(0)

    if opts.info_font:
        print(FigletFont.infoFont(opts.font))
        exit(0)

    if len(args) == 0:
        parser.print_help()
        return 1

    fontkwargs = {}
    if opts.smushmode:
        fontkwargs['smushMode'] = opts.smushmode

    text = ' '.join(args)

    f = Figlet(
        font=opts.font, direction=opts.direction,
        justify=opts.justify, width=opts.width, fontkwargs=fontkwargs,
    )

    r = f.renderText(text)
    if opts.reverse:
        r = r.reverse()
    if opts.flip:
        r = r.flip()

    if sys.version_info > (3,):
        # Set stdout to binary mode
        sys.stdout = sys.stdout.detach()

    if not opts.animate:
        sys.stdout.write((r + '\n').encode('UTF-8'))
    else:
        r = f.animate(text)
        sys.stdout.write((r + '\n').encode('UTF-8'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

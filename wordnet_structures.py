#!/usr/bin/env python
#Copyright 2007,2008 Sebastian Hagen
# This file is part of wordnet_tools.

# wordnet_tools is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2
# as published by the Free Software Foundation

# wordnet_tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with wordnet_tools; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

# This program requires python >= 2.4.

# This program converts wordnet index/data file pairs into dict index/data
# files usable by dictd.
# This is basically a reimplementation of the wnfilter program by Rik Faith,
# which unfortunately doesn't work correctly for wordnet files in the newer
# formats. This version of wordnet_structures should parse wordnet 3.0 files
# correctly, and create output very similar to what wnfilter would have 
# written.

import datetime
from textwrap import TextWrapper

try:
   import fcntl
except ImportError:
   fcntl = None

CAT_ADJECTIVE = 0
CAT_ADVERB = 1
CAT_NOUN = 2
CAT_VERB = 3

category_map = {
   'n': CAT_NOUN,
   'v': CAT_VERB,
   'a': CAT_ADJECTIVE,
   's': CAT_ADJECTIVE,
   'r': CAT_ADVERB
}

class SynsetWrapperDirect:
   __slots__ = ('s',)
   def __init__(self, index, synset_map):
      self.s = synset_map[index]
   def synset_get(self):
      return self.s


class SynsetWrapperPointer:
   __slots__ = ('index', 'map')
   def __init__(self, index, synset_map):
      self.index = index
      self.map = synset_map
   def synset_get(self):
      return self.map[self.index]
   def __repr__(self):
      return '%s(%s)' % (self.__class__.__name__, (self.index, self.synset_map))


class WordIndex:
   __slots__ = ('lemma', 'category', 'ptrs', 'synsets', 'tagsense_count')
   def __init__(self, lemma, category, ptrs, synsets, tagsense_count):
      self.lemma = lemma
      self.category = category
      self.ptrs = ptrs
      self.synsets = synsets
      self.tagsense_count = tagsense_count
   
   @classmethod
   def build_from_line(cls, line_data, synset_map, synset_wrap=SynsetWrapperPointer):
      line_split = line_data.split()
      lemma = line_split[0].replace('_',' ')
      category = category_map[line_split[1]]
      synset_count = int(line_split[2],10)
      ptr_count = int(line_split[3],10)
      ptrs = [line_split[i] for i in range(3, 3+ptr_count)]
      tagsense_count = int(line_split[5 + ptr_count],10)
      synsets = [synset_wrap(int(line_split[i],10), synset_map) for i in range(6 + ptr_count, 6 + ptr_count + synset_count)]
      return cls(lemma, category, ptrs, synsets, tagsense_count)
   
   @classmethod
   def build_from_file(cls, f, synset_map, synset_wrap=SynsetWrapperPointer, rv_base=None):
      if (rv_base is None):
         rv = {}
      else:
         rv = rv_base
         
      for line in f:
         if (line.startswith('  ')):
            continue
         wi = cls.build_from_line(line, synset_map, synset_wrap)
         word = wi.lemma.lower()
         if not (word in rv):
            rv[word] = []
         rv[word].append(wi)
      return rv

   def __repr__(self):
      return '%s%s' % (self.__class__.__name__, (self.lemma, self.category, self.ptrs, self.synsets, self.tagsense_count))
   
   
class WordIndexDictFormatter(WordIndex):
   category_map_rev = {
      CAT_NOUN: 'n',
      CAT_VERB: 'v',
      CAT_ADJECTIVE: 'adj',
      CAT_ADVERB: 'adv'
   }
   linesep = '\n'
   LINE_WIDTH_MAX = 68
   prefix_fmtf_line_first = '    %s 1: '
   prefix_fmtn_line_first = '        %*s'
   prefix_fmtf_line_nonfirst = '    %d: '
   prefix_fmtn_line_nonfirst = '    %*s  '
   
   def dict_str(self):
      """Build a human-readable definition for this word, including data for each synset"""
      tw = TextWrapper(width=self.LINE_WIDTH_MAX,
         initial_indent=(self.prefix_fmtf_line_first % self.category_map_rev[self.category]),
         subsequent_indent=(self.prefix_fmtn_line_first % (len(self.category_map_rev[self.category]), '')))
         
      lines = (tw.wrap(self.synsets[0].synset_get().dict_str()))
      i = 2
      
      prefix_fmtn_line_nonfirst = self.prefix_fmtn_line_nonfirst
      pfln_len = 0
      for ss_wrap in self.synsets[1:]:
         # adjust indenting based on index-number with
         pfln_len_new = len('%d' % (i,))
         if (pfln_len_new > pfln_len):
            pfln_len = pfln_len_new
            pfln_str = (self.prefix_fmtn_line_nonfirst % (pfln_len, ''))
         
         # format data for this synset
         synset = ss_wrap.synset_get()
         tw = TextWrapper(width=self.LINE_WIDTH_MAX,
            initial_indent=(self.prefix_fmtf_line_nonfirst % i),
            subsequent_indent=pfln_str)
         lines.extend(tw.wrap(synset.dict_str()))
         
         i += 1
         
      return self.linesep.join(lines)


class Synset:
   __slots__ = ('offset', 'type', 'words', 'ptrs', 'gloss', 'frames', 'synset_map')
   def __init__(self, offset, ss_type, words, ptrs, gloss, frames=(), synset_map=None):
      self.offset = offset
      self.type = ss_type
      self.words = words
      self.ptrs = ptrs
      self.gloss = gloss
      self.frames = frames
      self.synset_map = synset_map
   
   @classmethod
   def build_from_line(cls, line_data, synset_map=None):
      """Build instance from provided line from a wordnet data file.
      
      The optional synset_map argument will be passed to the instance constructor."""
      line_split = line_data.split()
      synset_offset = int(line_split[0],10)
      ss_type = category_map[line_split[2]]
      word_count = int(line_split[3],16)
      words = [line_split[i].replace('_',' ') for i in range(4, 4 + word_count*2,2)]
      ptr_count = int(line_split[4 + word_count*2],10)
      ptrs = [(line_split[i], # pointer symbol
         int(line_split[i+1],10), # synset offset
         category_map[line_split[i+2]], # synset type
         (int(line_split[i+3][:2],16), int(line_split[i+3][2:],16))) # offsets of specifically related words
         for i in range(5 + word_count*2,4 + word_count*2 + ptr_count*4,4)]
      
      tok = line_split[5 + word_count*2 + ptr_count*4]
      base = 6 + word_count*2 + ptr_count*4
      if (tok != '|'):
         frame_count = int(tok, 10)
         frames = [(int(line_split[i+1],10), int(line_split[i+2],16)) for i in range(base, base + frame_count*3, 3)]
         base += frame_count*3 + 1
      else:
         frames = []
      
      line_split2 = line_data.split(None, base)
      if (len(line_split2) < base):
         gloss = None
      else:
         gloss = line_split2[-1]
      
      return cls(synset_offset, ss_type, words, ptrs, gloss, frames, synset_map)
   
   @classmethod
   def build_from_file(cls, f):
      rv = {}
      comments = []
      
      for line in f:
         if (line.startswith('  ')):
            line_s = line.lstrip().rstrip('\n')
            line_elements = line_s.split(None,1)
            try:
               int(line_elements[0])
            except ValueError:
               continue
            if (len(line_elements) == 1):
               line_elements.append('')
            comments.append(line_elements[1])
            continue
         synset = cls.build_from_line(line.rstrip(), rv)
         rv[synset.offset] = synset

      return (rv, comments)

   def dict_str(self):
      """Format this synset into a human-readable line-wrapped dict block."""
      rv = self.gloss.rstrip()
      if (len(self.words) > 1):
         rv += ' [syn: %s]' % (', '.join([('{%s}' % word) for word in self.words]))
      
      if not (self.synset_map is None):
         antonyms = []
         for (ptr_symbol, synset_offset, synset_type, sourcetarget) in self.ptrs:
            if ((synset_type == self.type) and (ptr_symbol == '!')):
               ss = self.synset_map[synset_offset]
               antonyms.extend(ss.words)
      
         antonyms = list(set(antonyms)) # remove any duplicate entries
         antonyms.sort()
         if (antonyms):
            rv += ' [ant: %s]' % (', '.join([('{%s}' % word) for word in antonyms]))
      
      return rv

   def __repr__(self):
      return '%s%s' % (self.__class__.__name__, (self.offset, self.type, self.words, self.ptrs, self.gloss, self.frames, self.synset_map))


class SynsetFileBackedMapping:
   """Access a wordnet synset file as a mapping"""
   def __init__(self, f, file_lock=True, lock_block=False):
      self.file = f
      if (file_lock):
         if (fcntl is None):
            raise EnvironmentError('Unable to perform file locking without fcntl module')
         lock_op = fcntl.LOCK_SH
         if not (lock_block):
            lock_op |= fcntl.LOCK_NB
         fcntl.lockf(f.fileno(), lock_op)
      
   def __getitem__(self, key):
      self.file.seek(key)
      return Synset.build_from_line(self.file.readline().rstrip('\n'), self)

   def initial_comments_get(self):
      self.file.seek(0)
      comments = []
      for line in self.file:
         if not (line.startswith('  ')):
            break
         line_s = line.lstrip().rstrip('\n')
         line_elements = line_s.split(None,1)
         try:
            int(line_elements[0])
         except ValueError:
            continue
         if (len(line_elements) == 1):
            line_elements.append('')
         comments.append(line_elements[1])
         continue
      return comments


class WordnetDict:
   db_info_fmt = '''This file was converted from the original database on:
          %(conversion_datetime)s

The original data is available from:
     %(wn_url)s

The original data was distributed with the notice shown below. No
additional restrictions are claimed.  Please redistribute this changed
version under the same conditions and restriction that apply to the
original version.\n\n
%(wn_license)s'''

   datetime_fmt = '%Y-%m-%dT%H:%M:%S'
   base64_map = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
   
   def __init__(self, wn_url, desc_short, desc_long):
      self.word_data = {}
      self.wn_url = wn_url
      self.desc_short = desc_short
      self.desc_long = desc_long
      self.wn_license = None
   
   def wn_dict_add(self, file_index, file_data, synset_wrap_cls=SynsetWrapperDirect):
      file_data.seek(0)
      file_index.seek(0)
      synsets = SynsetFileBackedMapping(file_data)
      license_lines = synsets.initial_comments_get()
      WordIndexDictFormatter.build_from_file(file_index, synsets,
            synset_wrap=synset_wrap_cls, rv_base=self.word_data)
      if (license_lines):
         self.wn_license = '\n'.join(license_lines) + '\n'
   
   @classmethod
   def base64_encode(cls, i):
      """Encode a non-negative integer into a dictd compatible base64 string"""
      if (i < 0):
         raise ValueError('Value %r for i is negative' % (i,))
      r = 63
      e = 1
      while (r < i):
         e += 1
         r = 64**e - 1
      
      rv = ''
      while (e > 0):
         e -= 1
         d = (i / 64**e)
         rv += cls.base64_map[d]
         i = i % (64**e)
      return rv
      
   @classmethod
   def dict_entry_write(cls, file_index, file_data, key, entry, linesep='\n'):
      """Write a single dict entry for <key> to index and data files"""
      entry_start = file_data.tell()
      file_data.write(entry)
      entry_len = len(entry)
      file_index.write('%s\t%s\t%s%s' % (key, cls.base64_encode(entry_start),
            cls.base64_encode(entry_len), linesep))
      
   def dict_generate(self, file_index, file_data):
      file_index.seek(0)
      file_data.seek(0)
      # The dictd file format is fairly iffy on the subject of special
      # headwords: either dictd is buggy, or the manpage doesn't tell the whole
      # story about the format.
      # The upshot is that order of these entries in the index *matters*.
      # Putting them at the beginning and in alphabetic order is afaict ok.
      # Some other orders completely and quietly break the ability to look 
      # those headwords up.
      # -- problem encountered with 1.10.2, at 2007-08-05.
      file_data.write('\n')
      wn_url = self.wn_url
      conversion_datetime = datetime.datetime.now().strftime(self.datetime_fmt)
      wn_license = self.wn_license

      word_data = self.word_data.copy()
      for (key, value) in (
            ('00-database-allchars', '\n'),
            ('00-database-info', '00-database-info\n%s\n' % (self.db_info_fmt % vars())),
            ('00-database-long', '00-database-long\n%s\n' % self.desc_long),
            ('00-database-short', '00-database-short\n%s\n' % self.desc_short),
            ('00-database-url', '00-database-url\n%s\n' % self.wn_url)):
         word_data[key] = value
      
      words = word_data.keys()
      words.sort()
      
      for word in words:
         wval = word_data[word]
         if (isinstance(wval, basestring)):
            # special case: preformatted entries
            self.dict_entry_write(file_index, file_data, word, wval)
            continue
         
         for wi in wval:
            word_cs = word
            # Use case-sensitivity information of first entry of first synset that
            # matches this word case-insensitively
            for ss_wrapper in wi.synsets:
               synset = ss_wrapper.synset_get()
               for ss_word in synset.words:
                  if (ss_word.lower() == word_cs.lower()):
                     word_cs = ss_word
                     break
               else:
                  continue
               break
            else:
               continue
            break
            
         outstr = ''
         for wi in wval:
            outstr += wi.dict_str() + '\n'
         
         outstr = '%s%s%s' % (word_cs, wi.linesep, outstr)
         self.dict_entry_write(file_index, file_data, word, outstr, wi.linesep)
      
      file_index.truncate()
      file_data.truncate()


if (__name__ == '__main__'):
   import optparse
   op = optparse.OptionParser(usage='usage: %prog [options] (<wn_index_file> <wn_data_file>)+')
   op.add_option('-i', '--outindex', dest='oi', default='wn.index', help='filename of index file to write to')
   op.add_option('-d', '--outdata', dest='od', default='wn.dict', help='filename of data file to write to')
   op.add_option('--wn_url', dest='wn_url', default='ftp://ftp.cogsci.princeton.edu/pub/wordnet/2.0', help='URL for wordnet sources')
   op.add_option('--db_desc_short', dest='desc_short', default='     WordNet (r) 3.0 (2006)', help='short dict DB description')
   op.add_option('--db_desc_long', dest='desc_long', default='    WordNet (r): A Lexical Database for English from the\n     Cognitive Science Laboratory at Princeton University', help='long dict DB description')
   
   (options, args) = op.parse_args()
   
   wnd = WordnetDict(wn_url=options.wn_url, desc_short=options.desc_short, desc_long=options.desc_long)
   
   for i in range(0,len(args),2):
      print 'Opening index file %r...' % args[i]
      file_index = file(args[i])
      print 'Opening data file %r...' % args[i+1]
      file_data = file(args[i+1])
      print 'Parsing index file...'
      wnd.wn_dict_add(file_index, file_data, synset_wrap_cls=SynsetWrapperPointer)

   print 'All index files parsed. Parsing data input files and writing output to index file %r and data file %r.' % (options.oi, options.od)
   
   wnd.dict_generate(file(options.oi, 'w'),file(options.od, 'w'))
   print 'All done.'


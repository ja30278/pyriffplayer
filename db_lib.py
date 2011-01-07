#!/usr/bin/env python
"""
Copyright (c) 2008 Jon Allie <jon@jonallie.com>
 
Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:
 
The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.
 
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""

__author__ = 'Jon Allie (jon@jonallie.com)'


import hashlib
import httplib
import logging
import os
import sqlite3
import urllib
import urllib2

DEFAULT_DB_FILE = 'riffdb.sqlite'
DEFAULT_REMOTE_URL = 'http://www.openriff.com/db'
HASH_SAMPLE_SIZE = 26214400 # 25 megs

class Error(Exception):
  """Base level error."""

class OperationError(Error):
  """Operation Error."""


def calculate_hash(filename):
  hash_val = hashlib.md5()
  try:
    hash_val.update(open(filename).read(HASH_SAMPLE_SIZE))
  except (IOError, OSError, TypeError), e:
    raise OperationError(e)
  return hash_val.hexdigest()


class RiffDatabase(object):
  """Base class for a database mapping file hashes to offsets."""
  
  def add_offset(self, video_file, audio_file, offset):
    video_hash = calculate_hash(video_file)
    logging.debug('Video hash %s', video_hash)
    audio_hash = calculate_hash(audio_file)
    logging.debug('Audio hash %s', audio_hash)
    return self._add_offset(video_hash, audio_hash, offset)

  def get_offset(self, video_file, audio_file):
    video_hash = calculate_hash(video_file)
    audio_hash = calculate_hash(audio_file)
    return self._get_offset(video_hash, audio_hash)


class RemoteRiffDatabase(RiffDatabase):
  """A network-backed riff database."""

  def __init__(self, url):
    self.url = url

  def _add_offset(self, video_hash, audio_hash, offset):
    data = urllib.urlencode(
      dict(video_hash=video_hash, audio_hash=audio_hash, offset=offset))
    try:
      response = urllib2.urlopen(self.url, data=data)
      logging.debug('Remote response: %s', response)
    except urllib2.URLError, e:
      raise OperationError(e)

  def _get_offset(self, video_hash, audio_hash):
    data = urllib.urlencode(
      dict(video_hash=video_hash, audio_hash=audio_hash))
    url = '%s?%s' % (self.url, data)
    logging.debug('Requesting offset from url: %s', url)
    try:
      response = urllib2.urlopen(url).read()
      if response:
        logging.debug('Response: %s', response)
        return float(response)
      else:
        return None
    except Exception, e:
      raise OperationError(e)
    

class LocalRiffDatabase(RiffDatabase):
  """A riff database backed by a local Sqlite file."""

  _INIT_SQL = """
  DROP TABLE IF EXISTS `Offsets`;
  DROP INDEX IF EXISTS `Offsets-VideoAudio`;

  CREATE TABLE `Offsets`(
    `VideoFileHash` TEXT NOT NULL,
    `AudioFileHash` TEXT NOT NULL,
    `Offset` REAL NOT NULL);

  CREATE UNIQUE INDEX `Offsets-VideoAudio`
    ON `Offsets`(VideoFileHash,AudioFileHash);
  """

  _ADD_OFFSET_SQL = """
  INSERT OR REPLACE INTO Offsets(VideoFileHash, AudioFileHash, Offset)
    VALUES(?, ?, ?)
  """

  _GET_OFFSET_SQL = """
  SELECT Offset
  FROM Offsets
  WHERE VideoFileHash = ? AND AudioFileHash = ?
  """
  
  def __init__(self, path, overwrite=False):
    self._con = self._open_db(path, overwrite)
    self._con.text_factory = str

  def _add_offset(self, video_hash, audio_hash, offset):
    results = self._con.execute(
      _ADD_OFFSET_SQL, (video_hash, audio_hash, offset))
    self._con.commit()

  def _get_offset(self, video_hash, audio_hash):
    results = self._con.execute(
      _GET_OFFSET_SQL, (video_hash, audio_hash)).fetchone()
    if results:
      return results[0]
    else:
      return None

  def _init_db(self, path):
    try:
      handle = sqlite3.connect(path)
      handle.executescript(_INIT_SQL)
      handle.commit()
    except sqlite3.OperationalError, e:
      raise OperationError(e)
    return handle
  
  def _open_db(self, path, overwrite):
    if not os.path.exists(path) or overwrite:
      return self._init_db(path)
    try:
      handle = sqlite3.connect(path)
    except sqlite3.OperationalError, e:
      raise OperationError(e)
    else:
      return handle


def GetRiffDatabase(force_local=False):
  """Return a remote database if possible, or a local db otherwise."""
  if force_local:
    return LocalRiffDatabase(DEFAULT_DB_FILE)
  try:
    urllib2.urlopen(DEFAULT_REMOTE_URL)
    return RemoteRiffDatabase(DEFAULT_REMOTE_URL)
  except urllib2.URLError:
    return LocalRiffDatabase(DEFAULT_DB_FILE)

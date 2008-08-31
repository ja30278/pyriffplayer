#!/usr/bin/env python
"""File offset database library"""

import hashlib
import os
import sqlite3

class Error(Exception):
  """Base level error."""

class OperationError(Error):
  """Operation Error."""

_INIT_SQL = """
DROP TABLE IF EXISTS `Files`;
DROP TABLE IF EXISTS `Offsets`;
DROP INDEX IF EXISTS `Files-Hash`;
DROP INDEX IF EXISTS `Offsets-Offset`;

CREATE TABLE `Files`(
  `Id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `Hash` TEXT NOT NULL,
  `Filename` TEXT NULL);

CREATE UNIQUE INDEX `Files-Hash`
  ON `Files`(Hash);

CREATE TABLE `Offsets`(
  `VideoFileId` INTEGER NOT NULL,
  `AudioFileId` INTEGER NOT NULL,
  `Offset` REAL NOT NULL);

CREATE UNIQUE INDEX `Offsets-VideoAudio`
  ON `Offsets`(VideoFileId,AudioFileID);
"""

_ADD_FILE_SQL = """
INSERT INTO Files(Hash, Filename)
  VALUES(?, ?)
"""

_ADD_OFFSET_SQL = """
INSERT OR REPLACE INTO Offsets(VideoFileId, AudioFileId, Offset)
  VALUES(?, ?, ?)
"""

_GET_FILE_SQL = """
SELECT Id
FROM Files
WHERE Hash = ?
"""

_GET_OFFSET_SQL = """
SELECT o.Offset
FROM Offsets AS o
LEFT JOIN Files AS vf ON vf.Id = o.VideoFileID
LEFT JOIN Files AS af ON af.Id = o.AudioFileID 
WHERE vf.Hash = ? AND af.Hash = ?
"""


class RiffDatabase(object):
  
  def __init__(self, path, overwrite=True):
    self.path = path
    self.overwrite = overwrite
    self.con = self.open_db(self.path)
    self.con.text_factory = str

  @staticmethod
  def calculate_hash(filename):
    read_amount = 10485760  # 10 megs
    hash_val = hashlib.md5()
    try:
      hash_val.update(open(filename).read(read_amount))
    except (IOError, OSError), e:
      raise OperationError(e)
    return hash_val.digest()

  def _get_file_id(self, path):
    hash_val = RiffDatabase.calculate_hash(path)
    results = self.con.execute(_GET_FILE_SQL, (hash_val,)).fetchone()
    if results:
      return results[0]
    else:
      return None

  def add_file(self, path):
    hash_val = RiffDatabase.calculate_hash(path)
    results = self.con.execute(_ADD_FILE_SQL, (hash_val, path))
    self.con.commit()
    return results.lastrowid

  def add_offset(self, video_file, audio_file, offset):
    video_id = self._get_file_id(video_file) or self.add_file(video_file)
    print 'Video id %s' % video_id
    audio_id = self._get_file_id(audio_file) or self.add_file(audio_file)
    print 'Audio id %s' % audio_id
    results = self.con.execute(_ADD_OFFSET_SQL, (video_id, audio_id, offset))
    self.con.commit()

  def get_offset(self, video_file, audio_file):
    video_hash = RiffDatabase.calculate_hash(video_file)
    audio_hash = RiffDatabase.calculate_hash(audio_file)
    results = self.con.execute(_GET_OFFSET_SQL, (video_hash, audio_hash)).fetchone()
    if results:
      return results[0]
    else:
      return None

  def init_db(self, path):
    try:
      handle = sqlite3.connect(path)
      handle.executescript(_INIT_SQL)
      handle.commit()
    except sqlite3.OperationalError, e:
      raise OperationError(e)
    return handle
  
  def open_db(self, path):
    if not os.path.exists(path) or self.overwrite:
      return self.init_db(path)
    try:
      handle = sqlite3.connect(path)
    except sqlite3.OperationalError, e:
      raise OperationError(e)
    else:
      return handle

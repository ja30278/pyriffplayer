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
# vim:expandtab:sw=2 ts=2

import logging
import os
import sys
import time

import wx
import wx.media

import db_lib

RIFF_FILE_FILTER = 'MP3 Files (*.mp3)|*.mp3|AAC Files (*.aac)|*.aac'
#VIDEO_FILE_FILTER = ('AVI Files (*.avi)|*.avi|MPEG2 Files (*.mp[e]g)|*.mpg;*.mpeg2|'
#                    'MPEG4 Files (*.mp4)|*.mp4')
VIDEO_FILE_FILTER = '*.*'

DEFAULT_DB_FILE = 'riffdb.sqlite'

class AudioFrame(wx.Frame):
  """Separate audio frame."""
  def __init__(self, parent, id, title):
    wx.Frame.__init__(self, parent, wx.ID_ANY, title)

class RiffPlayerFrame(wx.Frame):

  def __init__(self, parent, id, title):
    """Initialize the main riff player frame."""
    wx.Frame.__init__(self, parent, wx.ID_ANY, title, size = (700, 500))
    self.Bind(wx.EVT_CLOSE, self.Destroy)
    self.SetMinSize((700, 500))

    self.video_file = None
    self.riff_file = None
    self.db_file = None
    self.db = None
    self.synced = False
    self._sync_done = False
    self.offset = 0

    self._InitControls()
    self._InitMenu()

  def _InitControls(self):
    self.video = wx.media.MediaCtrl(self)
    self.video.SetBackgroundColour('#000000')
    # each MediaCtrl must belong to a different frame
    audio_frame = AudioFrame(self, None, '')
    self.riff = wx.media.MediaCtrl(audio_frame)

    control_box = wx.BoxSizer(wx.VERTICAL)
    controls1 = wx.BoxSizer(wx.HORIZONTAL)
    controls2 = wx.BoxSizer(wx.HORIZONTAL)
    controls3 = wx.BoxSizer(wx.HORIZONTAL)
    
    self.video_slider = wx.Slider(self, -1, 0, 0, 1000)
    self.video_timer = wx.StaticText(self, -1, ' 00:00:00')
    self.video_select_button = wx.Button(self, -1, 'Video', size=(80, 30))
    self.riff_slider = wx.Slider(self, -1, 0, 0, 1000)
    self.riff_timer = wx.StaticText(self, -1, ' 00:00:00')
    self.riff_select_button = wx.Button(self, -1, 'Riff', size=(80, 30))
    self.play_button = wx.Button(self, -1, 'Play')
    self.play_button.Disable()
    self.sync_button = wx.ToggleButton(self, -1, 'Sync Lock')
    self.offset_timer = wx.StaticText(self, -1, 'Offset: 0.0')
    self.save_offset_button = wx.Button(self, -1, 'Save')
    self.video_volume_label = wx.StaticText(self, -1, 'Video Volume:')
    self.video_volume_slider = wx.Slider(self, -1, 50, 0, 100)
    self.riff_volume_label = wx.StaticText(self, -1, 'Riff Volume:')
    self.riff_volume_slider = wx.Slider(self, -1, 50, 0, 100)

    controls1.Add(self.video_select_button, 0, wx.ALL, 5)
    controls1.Add(self.video_slider, 1, wx.ALL|wx.EXPAND, 5)
    controls1.Add(self.video_timer, 0, wx.ALL, 5)
    controls2.Add(self.riff_select_button, 0, wx.ALL, 5)
    controls2.Add(self.riff_slider, 1, wx.ALL|wx.EXPAND, 5)
    controls2.Add(self.riff_timer, 0, wx.ALL, 5)
    controls3.Add(self.play_button, 0, wx.ALL, 5)
    controls3.Add(self.sync_button, 0, wx.ALL, 5)
    controls3.Add(self.offset_timer, 0, wx.ALL | wx.ALIGN_CENTRE, 5)
    controls3.Add(self.save_offset_button, 0, wx.ALL, 5)
    controls3.AddStretchSpacer()
    controls3.Add(self.video_volume_label, 0, wx.ALL, 5)
    controls3.Add(self.video_volume_slider, 1, wx.EXPAND | wx.ALL, 5)
    controls3.Add(self.riff_volume_label, 0, wx.ALL, 5)
    controls3.Add(self.riff_volume_slider, 1, wx.EXPAND | wx.ALL, 5)
    control_box.Add(controls1, 1, flag=wx.EXPAND)
    control_box.Add(controls2, 1, flag=wx.EXPAND)
    control_box.Add(controls3, 1, flag=wx.EXPAND)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.video, 1, flag=wx.EXPAND)
    sizer.Add(control_box, 0, flag=wx.EXPAND)
    self.SetSizer(sizer)
    self.Layout()

    self.Bind(wx.EVT_BUTTON, self.OnPlayPause, self.play_button)
    self.Bind(wx.EVT_BUTTON, self.OnChooseRiff, self.riff_select_button)
    self.Bind(wx.EVT_BUTTON, self.OnChooseVideo, self.video_select_button)
    self.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggleSync, self.sync_button)
    self.Bind(wx.EVT_BUTTON, self.OnSaveOffset, self.save_offset_button)
    self.Bind(wx.EVT_SLIDER, self.OnVideoSliderUpdate, self.video_slider)
    self.Bind(wx.EVT_SLIDER, self.OnRiffSliderUpdate, self.riff_slider)
    self.Bind(wx.EVT_SLIDER, self.OnVideoVolumeSliderUpdate,
              self.video_volume_slider)
    self.Bind(wx.EVT_SLIDER, self.OnRiffVolumeSliderUpdate,
              self.riff_volume_slider)

    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)
    self.Bind(wx.EVT_IDLE, self.OnIdle)


  def _InitMenu(self):
    self.menu_bar = wx.MenuBar()
    self.file_menu = wx.Menu()
    self.control_menu = wx.Menu()
    self.tools_menu = wx.Menu()

    self.menu_video_select = wx.MenuItem(self.file_menu, -1, 'Select &Video')
    self.menu_riff_select = wx.MenuItem(self.file_menu, -1, 'Select &Riff')
    self.menu_db_select = wx.MenuItem(self.file_menu, -1, 'Select &Database')
    self.file_menu.AppendItem(self.menu_video_select)
    self.file_menu.AppendItem(self.menu_riff_select)
    self.file_menu.AppendItem(self.menu_db_select)

    self.menu_play = wx.MenuItem(self.control_menu, -1, '&Play/Pause')
    self.menu_sync = wx.MenuItem(self.control_menu, -1, '&Sync Lock')
    self.control_menu.AppendItem(self.menu_play)
    self.control_menu.AppendItem(self.menu_sync)

    self.menu_hashes = wx.MenuItem(self.tools_menu, -1, 'Show &Hashes')
    self.menu_enter_offset = wx.MenuItem(self.tools_menu, -1, 'Enter &Offset')
    self.menu_save_offset = wx.MenuItem(self.tools_menu, -1, '&Save Offset')
    self.tools_menu.AppendItem(self.menu_hashes)
    self.tools_menu.AppendItem(self.menu_enter_offset)
    self.tools_menu.AppendItem(self.menu_save_offset)

    self.menu_bar.Append(self.file_menu, '&File')
    self.menu_bar.Append(self.control_menu, '&Controls')
    self.menu_bar.Append(self.tools_menu, '&Tools')
    self.SetMenuBar(self.menu_bar)

    self.Bind(wx.EVT_MENU, self.OnChooseVideo, self.menu_video_select)
    self.Bind(wx.EVT_MENU, self.OnChooseRiff, self.menu_riff_select)
    self.Bind(wx.EVT_MENU, self.OnChooseDb, self.menu_db_select)
    self.Bind(wx.EVT_MENU, self.OnPlayPause, self.menu_play)
    self.Bind(wx.EVT_MENU, self.OnToggleSync, self.menu_sync)
    self.Bind(wx.EVT_MENU, self.OnShowHash, self.menu_hashes)
    self.Bind(wx.EVT_MENU, self.OnEnterOffset, self.menu_enter_offset)
    self.Bind(wx.EVT_MENU, self.OnSaveOffset, self.menu_save_offset)


  def Play(self):
    self.video.Play()
    self.riff.Play()

  def Pause(self):
    self.video.Pause()
    self.riff.Pause()

  def Stop(self):
    self.video.Stop()
    self.riff.Stop()

  def OnPlayPause(self, event):
    """Event handler for play button events."""
    if not self.video_file or not self.riff_file:
      return
    self.video.SetVolume(.5)
    self.riff.SetVolume(.5)
    state = self.play_button.GetLabel()
    if state == 'Play':
      self.Play()
      self.play_button.SetLabel('Pause')
      logging.info('Volume: riff : %s', self.riff.GetVolume())
      try:
        vid_duration_milli = self.video.Length()
        riff_duration_milli = self.riff.Length()
        self.video_slider.SetValue(0)
        self.riff_slider.SetValue(0)
        self.video_slider.SetMax(vid_duration_milli)
        self.riff_slider.SetMax(riff_duration_milli)
      except Exception, e:
        logging.error('Error setting slider max values: %s', e)
    else:
      self.Pause()
      self.play_button.SetLabel('Play')

  def OnRiffSliderUpdate(self, event):
    """Event handler for the riff position slider."""
    pos = self.riff_slider.GetValue()
    try:
      self.riff.Seek(pos)
    except Exception, e:
      logging.error('Error performing riff slider sync: %s', e)

  def OnVideoSliderUpdate(self, event):
    pos = self.video_slider.GetValue()
    try:
      self.video.Seek(pos)
      self._ApplyOffset()
    except Exception, e:
      logging.error('Error performing video slider sync: %s', e)

  def OnVideoVolumeSliderUpdate(self, event):
    """Event handler for video volume adjustment."""
    volume = self.video_volume_slider.GetValue()/100.0
    self.video.SetVolume(volume)

  def OnRiffVolumeSliderUpdate(self, event):
    """Event handler for riff volume adjustment."""
    volume = self.riff_volume_slider.GetValue()/100.0
    self.riff.SetVolume(volume)

  def OnChooseRiff(self, event):
    """Event handler for riff selection."""
    self.riff_file = self._ChooseFile(filter=RIFF_FILE_FILTER)
    self.riff.Load(self.riff_file)
    logging.debug('Riff file: %s', self.riff_file)
    self.play_button.Enable()
    self._LoadOffset()
    self._ApplyOffset()
  
  def OnChooseVideo(self, event):
    """Event handler for video selection."""
    self.video_file = self._ChooseFile(filter=VIDEO_FILE_FILTER)
    self.video.Load(self.video_file)
    logging.debug('Video file: %s', self.video_file)
    self.play_button.Enable()
    self._LoadOffset()
    self._ApplyOffset()

  def OnChooseDb(self, event):
    """Event handler for database selection."""
    db_file = self._ChooseFile(mode=wx.SAVE)
    if db_file is None:
      return
    self.SetDbFile(db_file)

  def SetDbFile(self, filename):
    self.db_file = filename
    try:
      self.db = db_lib.RiffDatabase(self.db_file)
    except db_lib.OperationError, e:
      self._ErrorMsg('Error opening riff database: %s' % e)
    self._LoadOffset()
    self._ApplyOffset()

  def SetOffset(self, offset):
    logging.debug('Setting offset to: %s', offset)
    self.offset = offset
    self.synced = True
    self._ApplyOffset()

  def _CalculateOffset(self):
    """Calculate current riff->video offset.

    Returns:
      int - offset in milliseconds
    """
    offset = 0
    try:
      vid_position_milli = self.video.Tell()
      riff_position_milli = self.riff.Tell()
      offset = riff_position_milli - vid_position_milli
    except Exception, e:
      logging.error('Offset calculation error: %s', e)
    return offset

  def _LoadOffset(self):
    """Attempt to load offset for current files from db."""
    if None in (self.video_file, self.riff_file, self.db_file):
      return
    offset = self.db.get_offset(self.video_file, self.riff_file)
    if offset is not None:
      self.SetOffset(offset)


  def _ApplyOffset(self):
    """Apply current offset if required."""
    if not self.synced or None in (self.video_file, self.riff_file):
      return
    try:
      vid_position_milli = self.video.Tell()
      riff_duration_milli = self.riff.Length()
      riff_position_milli = self.riff.Length()
      new_riff_pos = min(riff_duration_milli, max(vid_position_milli + self.offset, 0))
      # allow for tiny amounts of drift to minimize seeking
      if abs(new_riff_pos - riff_position_milli) > 100:
        logging.debug('Sync: Seeking riff to: %s', new_riff_pos)
        self.riff.Seek(new_riff_pos)
    except Exception, e:
      logging.debug('Error applying offset: %s', e)
    
  def OnSaveOffset(self, event):
    """Event handler for saving offset value."""
    if None in (self.video_file, self.riff_file, self.db_file):
      self._ErrorMsg('Unable to save offset')
      return
    self.db.add_offset(self.video_file, self.riff_file, self.offset)
    logging.debug('Saved offset')
      
  def OnToggleSync(self, event):
    """Event handler for sync button."""
    self.synced = self.sync_button.GetValue()
    if not self.synced:
      self.save_offset_button.Disable()
      return
    state = self.play_button.GetLabel()
    if self.db_file:
      self.save_offset_button.Enable()
    if state == 'Pause':
      self.SetOffset(self._CalculateOffset())

  def OnIdle(self, event):
    """Event handler for the Idle task.
    
    Used to update non-gui background processes
    """
    if not int(time.time()) % 5:
      if not self._sync_done:
        self._ApplyOffset()
        self._sync_done = True
    else:
      self._sync_done = False

  def OnUpdateUI(self, event):
    """Event handler for the EVT_UPDATE_UI psuedo-signal."""
    self.offset_timer.SetLabel('Offset: %s' % self.offset)
    if self.synced:
      self.sync_button.SetValue(True)
      self.riff_slider.Disable()
    else:
      self.sync_button.SetValue(False)
      self.riff_slider.Enable()
    try:
      vid_duration_milli = self.video.Length()
      vid_position_milli = self.video.Tell()
      riff_duration_milli = self.riff.Length()
      riff_position_milli = self.riff.Tell()
    except Exception, e:
      logging.error('Error encountered obtaining postion/duration: %s', e)
      return
    self.video_timer.SetLabel(self._FormatTimestamp(vid_position_milli))
    self.video_slider.SetValue(vid_position_milli)
    self.riff_timer.SetLabel(self._FormatTimestamp(riff_position_milli))
    self.riff_slider.SetValue(riff_position_milli)
    
  def _ChooseFile(self, dirname='/', filter='*.*', mode=wx.OPEN):
    """Utility function for selecting a file.
    
    Args:
      dirname: starting directory
      mode: a wx mode constant

    Returns:
      str - the full path to the selected file
    """
    filename = None
    dlg = wx.FileDialog(self, 'Choose a file', dirname, '', filter, mode)
    if dlg.ShowModal() == wx.ID_OK:
      filename = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
    dlg.Destroy()
    return filename

  def _ErrorMsg(self, message):
    """Display an error message in a popup dialog."""
    dlg = wx.MessageDialog(self, message, 'Error', style=wx.OK | wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()
    

  def _FormatTimestamp(self, ts):
    """Format nanosecond timestamp as hours, minutes, seconds.
    
    Args:
      ts: timestamp value in nanoseconds
      
    Returns:
      str - formatted string: HH:MM:SS
    """
    secs = ts/1000
    return '%.2d:%.2d:%.2d' % (secs//3600, (secs%3600)//60, secs%60) 


  def OnShowHash(self, event):
    """Event handler for hash display."""
    vid_hash = riff_hash = None
    try:
      vid_hash = self.db.calculate_hash(self.video_file)
      riff_hash = self.db.calculate_hash(self.riff_file)
    except db_lib.OperationError, e:
      logging.error('Hash calculation error: %s', e)
    msg = 'Video Hash: %s\nRiff Hash: %s' % (vid_hash, riff_hash)
    dlg = wx.MessageDialog(self, msg, 'Hash Info',
                           style=wx.OK | wx.ICON_INFORMATION)
    dlg.ShowModal()
    dlg.Destroy()

  def OnEnterOffset(self, event):
    offset = None
    dlg = wx.NumberEntryDialog(self, 'Enter offset', 'Offset', 'Offset', 0, 0, 5000)
    if dlg.ShowModal() == wx.ID_OK:
      offset = dlg.GetValue()
    dlg.Destroy()
    if offset is not None:
      self.SetOffset(offset)

  def Destroy(self, event):
    event.Skip()


class RiffPlayer(wx.App):
  """The riffplayer app class."""

  def OnInit(self):
    frame = RiffPlayerFrame(None, -1, 'Riff Player')
    frame.SetDbFile(DEFAULT_DB_FILE)
    print 'got here'
    x = frame.Show(True)
    print x
    frame.Centre()

    return True

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  app = RiffPlayer(0)
  app.MainLoop()
    

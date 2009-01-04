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

import pygst
pygst.require('0.10')
import gst
import wx

import gobject
gobject.threads_init()

import db_lib

RIFF_FILE_FILTER = 'MP3 Files (*.mp3)|*.mp3|AAC Files (*.aac)|*.aac'
#VIDEO_FILE_FILTER = ('AVI Files (*.avi)|*.avi|MPEG2 Files (*.mp[e]g)|*.mpg;*.mpeg2|'
#                    'MPEG4 Files (*.mp4)|*.mp4')
VIDEO_FILE_FILTER = '*.*'

DEFAULT_DB_FILE = 'riffdb.sqlite'

class RiffPlayerFrame(wx.Frame):

  def __init__(self, parent, id, title):
    """Initialize the main riff player frame."""
    wx.Frame.__init__(self, parent, wx.ID_ANY, title, size = (700, 500))
    self.Bind(wx.EVT_CLOSE, self.Destroy)
    self.SetMinSize((700, 500))

    self.video_file = None
    self.video = None
    self.riff_file = None
    self.riff = None
    self.db_file = None
    self.db = None
    self.synced = False
    self._sync_done = False
    self.offset = 0

    self._InitControls()
    self._InitMenu()
    self._InitGstreamer()

  def _InitControls(self):
    self.video_panel = wx.Panel(self, -1)
    self.video_panel.SetBackgroundColour(wx.BLACK)

    control_box = wx.BoxSizer(wx.VERTICAL)
    controls1 = wx.BoxSizer(wx.HORIZONTAL)
    controls2 = wx.BoxSizer(wx.HORIZONTAL)
    controls3 = wx.BoxSizer(wx.HORIZONTAL)
    
    self.video_slider = wx.Slider(self, -1, 0, 0, 1000)
    self.video_timer = wx.StaticText(self, -1, '00:00:00')
    self.video_select_button = wx.Button(self, -1, 'Video', size=(80, 30))
    self.riff_slider = wx.Slider(self, -1, 0, 0, 1000)
    self.riff_timer = wx.StaticText(self, -1, '00:00:00')
    self.riff_select_button = wx.Button(self, -1, 'Riff', size=(80, 30))
    self.play_button = wx.Button(self, -1, 'Play')
    self.play_button.Disable()
    self.sync_button = wx.ToggleButton(self, -1, 'Sync Lock')
    self.offset_timer = wx.StaticText(self, -1, 'Offset: 0.0')
    self.save_offset_button = wx.Button(self, -1, 'Save')
    self.save_offset_button.Disable()
    self.video_volume_label = wx.StaticText(self, -1, 'Video Volume:')
    self.video_volume_slider = wx.Slider(self, -1, 5, 0, 10)
    self.riff_volume_label = wx.StaticText(self, -1, 'Riff Volume:')
    self.riff_volume_slider = wx.Slider(self, -1, 5, 0, 10)

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
    controls3.Add(self.video_volume_label, 0, wx.ALL | wx.ALIGN_CENTRE, 5)
    controls3.Add(self.video_volume_slider, 1, wx.ALL | wx.EXPAND, 5)
    controls3.Add(self.riff_volume_label, 0, wx.ALL | wx.ALIGN_CENTRE, 5)
    controls3.Add(self.riff_volume_slider, 1, wx.ALL | wx.EXPAND, 5)
    control_box.Add(controls1, 1, flag=wx.EXPAND)
    control_box.Add(controls2, 1, flag=wx.EXPAND)
    control_box.Add(controls3, 1, flag=wx.EXPAND)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.video_panel, 1, flag=wx.EXPAND)
    sizer.Add(control_box, 0, flag=wx.EXPAND)
    self.SetSizer(sizer)
    self.Layout()

    # bind events
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


  def _InitGstreamer(self):
    # set up gstreamer pipeline
    self.player = gst.Pipeline('player')

    self.riff = gst.element_factory_make('playbin', 'riff-pbin')
    self.riff.set_property('volume', 5.0)
    self.video = gst.element_factory_make('playbin', 'video-pbin')
    self.video.set_property('volume', 5.0)

    self.video_sink = gst.element_factory_make('autovideosink', 'video-sink')
    self.video.set_property('video-sink', self.video_sink)

    self.player.add(self.riff, self.video)
    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect('message', self.OnMessage)
    bus.connect('sync-message::element', self.OnSyncMessage)


  def OnPlayPause(self, event):
    """Event handler for play button events."""
    if not self.video_file or not self.riff_file:
      return
    state = self.play_button.GetLabel()
    if state == 'Play':
      self.player.set_state(gst.STATE_PLAYING)
      self.play_button.SetLabel('Pause')
      time.sleep(1)
      try:
        vid_duration_nano, _ = self.video.query_duration(gst.FORMAT_TIME)
        riff_duration_nano, _ = self.riff.query_duration(gst.FORMAT_TIME)
        self.video_slider.SetMax(vid_duration_nano / 1000000000)
        self.riff_slider.SetMax(riff_duration_nano / 1000000000)
      except Exception, e:
        logging.error('Error setting slider max values: %s', e)
    else:
      self.player.set_state(gst.STATE_PAUSED)
      self.play_button.SetLabel('Play')

  def OnVideoSliderUpdate(self, event):
    pos = self.video_slider.GetValue()
    pos *= 1000000000
    try:
      self.video.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, pos)
      self._ApplyOffset()
    except Exception, e:
      logging.error('Error performing video slider sync: %s', e)

  def OnVideoVolumeSliderUpdate(self, event):
    volume = float(self.video_volume_slider.GetValue())
    self.video.set_property('volume', volume)

  def OnRiffVolumeSliderUpdate(self, event):
    volume = float(self.riff_volume_slider.GetValue())
    self.riff.set_property('volume', volume)

  def OnRiffSliderUpdate(self, event):
    pos = self.riff_slider.GetValue()
    pos *= 1000000000
    try:
      self.riff.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, pos)
      # Seeking video to it's current position prevents odd freeze
      video_pos, _ = self.video.query_position(gst.FORMAT_TIME)
      self.video.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, video_pos)
    except Exception, e:
      logging.error('Error performing riff slider sync: %s', e)

  def OnChooseRiff(self, event):
    """Event handler for riff selection."""
    self.riff_file = self._ChooseFile(filter=RIFF_FILE_FILTER)
    self.riff.set_property('uri', 'file://%s' % self.riff_file)
    logging.debug('Riff file: %s', self.riff_file)
    self.play_button.Enable()
    self._LoadOffset()
    self._ApplyOffset()
  
  def OnChooseVideo(self, event):
    """Event handler for video selection."""
    self.video_file = self._ChooseFile(filter=VIDEO_FILE_FILTER)
    self.video.set_property('uri', 'file://%s' % self.video_file)
    logging.debug('Video file: %s', self.video_file)
    self.play_button.Enable()
    self._LoadOffset()
    self._ApplyOffset()

  def OnChooseDb(self, event):
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

  def _CalculateOffset(self):
    offset = 0
    try:
      vid_position_nano, _ = self.video.query_position(gst.FORMAT_TIME)
      riff_position_nano, _ = self.riff.query_position(gst.FORMAT_TIME)
      offset = (riff_position_nano - vid_position_nano) / 1000000000
    except Exception, e:
      logging.error('Offset calculation error: %s', e)
    return offset

  def _LoadOffset(self):
    if None in (self.video_file, self.riff_file, self.db_file):
      return
    offset = self.db.get_offset(self.video_file, self.riff_file)
    if offset is not None:
      self.SetOffset(offset)

  def SetOffset(self, offset):
    logging.debug('Setting offset to: %s', offset)
    self.offset = offset
    self.synced = True
    self._ApplyOffset()

  def _ApplyOffset(self):
    if not self.synced or None in (self.video_file, self.riff_file):
      return
    try:
      vid_position_nano, _ = self.video.query_position(gst.FORMAT_TIME)
      riff_duration_nano, _ = self.riff.query_duration(gst.FORMAT_TIME)
      riff_pos = min(riff_duration_nano, 
                     max(vid_position_nano + (self.offset * 1000000000), 0))
      logging.debug('Sync: Seeking riff to: %s', riff_pos)
      self.riff.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, riff_pos)
      # this second seek seems to prevent odd video freezes when seeking only the
      # audio track
      self.video.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, vid_position_nano)
    except Exception, e:
      logging.debug('Error applying offset: %s', e)
    
  def OnSaveOffset(self, event):
    if None in (self.video_file, self.riff_file, self.db_file):
      return
    self.db.add_offset(self.video_file, self.riff_file, self.offset)
    logging.debug('Saved offset')
      
  def OnToggleSync(self, event):
    """Event handler for sync button."""
    self.synced = self.sync_button.GetValue()
    if not self.synced:
      self.save_offset_button.Disable()
      return
    _, state, _ = self.player.get_state()
    if self.db_file:
      self.save_offset_button.Enable()
    if state == gst.STATE_PLAYING:
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
      vid_duration_nano, _ = self.video.query_duration(gst.FORMAT_TIME)
      vid_position_nano, _ = self.video.query_position(gst.FORMAT_TIME)
      riff_duration_nano, _ = self.riff.query_position(gst.FORMAT_TIME)
      riff_position_nano, _ = self.riff.query_position(gst.FORMAT_TIME)
    except Exception, e:
      # will be raised if stream isn't rolled for playback
      return
    self.video_timer.SetLabel(self._FormatTimestamp(vid_position_nano))
    self.video_slider.SetValue(vid_position_nano/1000000000)
    self.riff_timer.SetLabel(self._FormatTimestamp(riff_position_nano))
    self.riff_slider.SetValue(riff_position_nano/1000000000)
    
  def _ChooseFile(self, dirname='/', filter='*.*', mode=wx.OPEN):
    """Utility function for selecting a file.
    
    Args:
      dirname: starting directory

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
    dlg = wx.MessageDialog(self, message, 'Error', style=wx.OK | wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()
    

  def _FormatTimestamp(self, ts):
    """Format nanosecond timestamp as hours, minutes, seconds.
    
    Args:
      ts: timestamp value in nanoseconds
      
    Returns:
      str - formatted string: hh:mm:ss
    """
    secs = ts/1000000000
    return '%.2d:%.2d:%.2d' % (secs//3600, (secs%3600)//60, secs%60) 

  def OnMessage(self, bus, message):
    if message.type in (gst.MESSAGE_EOS, gst.MESSAGE_ERROR):
      self.player.set_state(gst.STATE_NULL)
      self.play_button.SetLabel('Play')

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


  def OnSyncMessage(self, bus, message):
    if message.structure is None:
      return
    message_name = message.structure.get_name()
    if message_name == 'prepare-xwindow-id':
      imagesink = message.src
      imagesink.set_property('force-aspect-ratio', True)
      imagesink.set_xwindow_id(self.video_panel.GetHandle())

  def Destroy(self, event):
    self.player.set_state(gst.STATE_NULL)
    event.Skip()


class RiffPlayer(wx.App):
  """The riffplayer app class."""

  def OnInit(self):
    frame = RiffPlayerFrame(None, -1, 'Riff Player')
    frame.SetDbFile(DEFAULT_DB_FILE)
    frame.Show(True)
    frame.Centre()
    return True

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  app = RiffPlayer(0)
  app.MainLoop()
    

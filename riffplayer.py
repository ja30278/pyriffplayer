#!/usr/bin/env python
"""
Copyright (c) 2008 Jon Allie <jon@jonallie.com>

Permission is hereby granted, free of charge, to any person
Obtaining a copy of this software and associated documentation
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

__version__ = '0.2'
GPL = __doc__

import logging
import os
import sys
import time

import wx
import wx.media

import db_lib

RIFF_FILE_FILTER = 'MP3 Files (*.mp3)|*.mp3|AAC Files (*.aac)|*.aac'
VIDEO_FILE_FILTER = '*.*'

DEFAULT_DB_FILE = 'riffdb.sqlite'
RES_DIR = 'res'

# Sizing related constants
_NO_RESIZE = 0
_LINEAR_RESIZE = 1


class AudioFrame(wx.Frame):
  """Separate audio frame."""
  def __init__(self, parent, id, title):
    wx.Frame.__init__(self, parent, wx.ID_ANY, title)

class RiffPlayerFrame(wx.Frame):

  def __init__(self, parent, title):
    """Initialize the main riff player frame."""
    wx.Frame.__init__(self, parent, wx.ID_ANY, title=title, size = (700, 500))
    self.Bind(wx.EVT_CLOSE, self.Destroy)
    self.SetMinSize((700, 500))

    self.video_file = None
    self.riff_file = None
    self.db_file = None
    self.db = None
    self.synced = False
    self.offset = 0


    self._InitResources()
    self._InitControls()
    self._InitMenu()

  def _InitResources(self):
    self.bmp = {
      'play': wx.Bitmap(os.path.join(RES_DIR, 'media-playback-start.png')),
      'pause': wx.Bitmap(os.path.join(RES_DIR, 'media-playback-pause.png')),
      'stop': wx.Bitmap(os.path.join(RES_DIR, 'media-playback-stop.png')),
      'video': wx.Bitmap(os.path.join(RES_DIR, 'emblem-videos.png')),
      'riff': wx.Bitmap(os.path.join(RES_DIR, 'emblem-sound.png')),
      'locked': wx.Bitmap(os.path.join(RES_DIR, 'locked.png')),
      'unlocked': wx.Bitmap(os.path.join(RES_DIR, 'unlocked.png')),
      'save': wx.Bitmap(os.path.join(RES_DIR, 'document-save.png')),
      'volume': wx.Bitmap(os.path.join(RES_DIR, 'audio-volume-high.png')),
      'fullscreen': wx.Bitmap(os.path.join(RES_DIR, 'view-fullscreen.png'))
     }

  def _InitControls(self):
    # The main video panel, defaulted to a black background
    self.video = wx.media.MediaCtrl(self)
    self.video.SetBackgroundColour('#000000')
    
    # The riff audio is handled by a separate MediaCtl instance which
    # is associated with its own frame
    audio_frame = AudioFrame(self, None, '')
    self.riff = wx.media.MediaCtrl(audio_frame)

    self.control_panel = wx.Panel(self)
    control_box = wx.BoxSizer(wx.VERTICAL)
    self.control_panel.SetSizer(control_box)

    self.video_select_button = wx.BitmapButton(self.control_panel,
                                               bitmap=self.bmp['video'])
    self.video_select_button.SetToolTip(wx.ToolTip('Select video'))

    self.video_slider = wx.Slider(self.control_panel, value=0, minValue=0,
                                  maxValue=1000)

    self.video_timer = wx.StaticText(self.control_panel, label=' 00:00:00')

    self.riff_select_button = wx.BitmapButton(self.control_panel,
                                              bitmap=self.bmp['riff'])
    self.riff_select_button.SetToolTip(wx.ToolTip('Select riff'))

    self.riff_slider = wx.Slider(self.control_panel, value=0, minValue=0, maxValue=1000)

    self.riff_timer = wx.StaticText(self.control_panel, label=' 00:00:00')

    self.play_button = wx.BitmapButton(self.control_panel, bitmap=self.bmp['play'])
    self.play_button.SetToolTip(wx.ToolTip('Start Playback'))

    self.stop_button = wx.BitmapButton(self.control_panel, bitmap=self.bmp['stop'])
    self.stop_button.SetToolTip(wx.ToolTip('Stop Playback'))

    self.fullscreen_button = wx.BitmapButton(self.control_panel,
                                             bitmap=self.bmp['fullscreen'])
    self.fullscreen_button.SetToolTip(wx.ToolTip('Toogle fullscreen'))

    self.sync_button = wx.BitmapButton(self.control_panel, bitmap=self.bmp['unlocked'])
    self.sync_button.SetToolTip(wx.ToolTip('Lock sync'))

    self.offset_button = wx.Button(self.control_panel, label='Offset: 0.0',
                                   style=wx.NO_BORDER)
    self.save_offset_button = wx.BitmapButton(self.control_panel,
                                              bitmap=self.bmp['save'])
    self.save_offset_button.SetToolTip(wx.ToolTip('Save Current Offset'))
    self.video_volume_label = wx.StaticText(self.control_panel, label='Video:')
    self.video_volume_bmp = wx.StaticBitmap(self.control_panel,
                                            bitmap=self.bmp['volume'])
    self.video_volume_slider = wx.Slider(self.control_panel, value=50,
                                         minValue=0, maxValue=100)
    self.riff_volume_label = wx.StaticText(self.control_panel, label='Riff:')
    self.riff_volume_bmp = wx.StaticBitmap(self.control_panel,
                                           bitmap=self.bmp['volume'])
    self.riff_volume_slider = wx.Slider(self.control_panel, value=50,
                                        minValue=0, maxValue=100)

    controls1 = wx.BoxSizer(wx.HORIZONTAL)
    controls2 = wx.BoxSizer(wx.HORIZONTAL)
    controls3 = wx.BoxSizer(wx.HORIZONTAL)
    
    controls1.Add(self.video_select_button, _NO_RESIZE, wx.ALL, 5)
    controls1.Add(self.video_slider, _LINEAR_RESIZE, wx.ALL|wx.EXPAND|wx.ALIGN_BOTTOM, 5)
    controls1.Add(self.video_timer, _NO_RESIZE, wx.ALL, 5)
    controls2.Add(self.riff_select_button, _NO_RESIZE, wx.ALL, 5)
    controls2.Add(self.riff_slider, _LINEAR_RESIZE, wx.ALL|wx.EXPAND, 5)
    controls2.Add(self.riff_timer, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.play_button, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.stop_button, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.fullscreen_button, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.sync_button, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.save_offset_button, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.offset_button, _NO_RESIZE, wx.ALL, 5)
    controls3.AddStretchSpacer()
    controls3.Add(self.video_volume_label, _NO_RESIZE, wx.ALL|wx.ALIGN_TOP, 5)
    controls3.Add(self.video_volume_bmp, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.video_volume_slider, _LINEAR_RESIZE, wx.ALL, 5)
    controls3.Add(self.riff_volume_label, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.riff_volume_bmp, _NO_RESIZE, wx.ALL, 5)
    controls3.Add(self.riff_volume_slider, _LINEAR_RESIZE, wx.ALL, 5)
    control_box.Add(controls1, _LINEAR_RESIZE, flag=wx.EXPAND)
    control_box.Add(controls2, _LINEAR_RESIZE, flag=wx.EXPAND)
    control_box.Add(controls3, _LINEAR_RESIZE, flag=wx.EXPAND)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.video, _LINEAR_RESIZE, flag=wx.EXPAND)
    sizer.Add(self.control_panel, _NO_RESIZE, flag=wx.EXPAND)
    self.SetSizer(sizer)
    self.Layout()

    self.Bind(wx.EVT_BUTTON, self.OnPlayPause, self.play_button)
    self.Bind(wx.EVT_BUTTON, self.OnStop, self.stop_button)
    self.Bind(wx.EVT_BUTTON, self.OnToggleFullscreen, self.fullscreen_button)
    self.Bind(wx.EVT_BUTTON, self.OnChooseRiff, self.riff_select_button)
    self.Bind(wx.EVT_BUTTON, self.OnChooseVideo, self.video_select_button)
    self.Bind(wx.EVT_BUTTON, self.OnToggleSync, self.sync_button)
    self.Bind(wx.EVT_BUTTON, self.OnSaveOffset, self.save_offset_button)
    self.Bind(wx.EVT_BUTTON, self.OnEnterOffset, self.offset_button)
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

    self.menu_video_select = wx.MenuItem(self.file_menu, wx.ID_ANY, 'Select &Video')
    self.menu_riff_select = wx.MenuItem(self.file_menu, wx.ID_ANY, '&Riff')
    self.menu_db_select = wx.MenuItem(self.file_menu, wx.ID_ANY, '&Database')
    self.file_menu.AppendItem(self.menu_video_select)
    self.file_menu.AppendItem(self.menu_riff_select)
    self.file_menu.AppendItem(self.menu_db_select)

    self.menu_play = wx.MenuItem(self.control_menu, wx.ID_ANY, '&Play/Pause')
    self.menu_sync = wx.MenuItem(self.control_menu, wx.ID_ANY, '&Sync Lock')
    self.control_menu.AppendItem(self.menu_play)
    self.control_menu.AppendItem(self.menu_sync)

    self.menu_hashes = wx.MenuItem(self.tools_menu, wx.ID_ANY, 'Show &Hashes')
    self.menu_enter_offset = wx.MenuItem(self.tools_menu, wx.ID_ANY,
                                         'Enter &Offset')
    self.menu_save_offset = wx.MenuItem(self.tools_menu, wx.ID_ANY,
                                        '&Save Offset')
    self.menu_about = wx.MenuItem(self.tools_menu, wx.ID_ANY, '&About')
    self.tools_menu.AppendItem(self.menu_hashes)
    self.tools_menu.AppendItem(self.menu_enter_offset)
    self.tools_menu.AppendItem(self.menu_save_offset)
    self.tools_menu.AppendItem(self.menu_about)

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
    self.Bind(wx.EVT_MENU, self.OnAbout, self.menu_about)


  def Play(self):
    self.play_button.SetBitmapLabel(self.bmp['pause'])
    self.video.Play()
    self.riff.Play()
    try:
      self.video_slider.SetMax(self.video.Length())
      self.riff_slider.SetMax(self.riff.Length())
    except Exception, e:
      logging.error('Error setting slider max values: %s', e)

  def Pause(self):
    self.play_button.SetBitmapLabel(self.bmp['play'])
    self.video.Pause()
    self.riff.Pause()

  def Stop(self):
    self.play_button.SetBitmapLabel(self.bmp['play'])
    self.video_slider.SetValue(0)
    self.riff_slider.SetValue(0)
    self.video.Stop()
    self.riff.Stop()

  def OnPlayPause(self, event):
    """Event handler for play button events."""
    if wx.media.MEDIASTATE_PLAYING in (self.video.GetState(),
                                       self.riff.GetState()):
      self.Pause()
    elif not self.video_file or not self.riff_file:
      return
    else:
      self.Play()

  def OnStop(self, event):
    self.Stop()

  def OnToggleFullscreen(self, event):
    show = self.IsFullScreen() is False
    self.ShowFullScreen(show)

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
    self.Stop()
    self.riff_file = self._ChooseFile(filter=RIFF_FILE_FILTER)
    self.riff.Load(self.riff_file)
    logging.debug('Riff file: %s', self.riff_file)
    self.play_button.Enable()
    self._LoadOffset()
    self._ApplyOffset()
  
  def OnChooseVideo(self, event):
    """Event handler for video selection."""
    self.Stop()
    self.video_file = self._ChooseFile(filter=VIDEO_FILE_FILTER)
    self.video.Load(self.video_file)
    logging.debug('Video file: %s', self.video_file)
    self.play_button.Enable()
    self._LoadOffset()
    self._ApplyOffset()

  def OnChooseDb(self, event):
    """Event handler for database selection."""
    self.Stop()
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
      riff_position_milli = self.riff.Tell()
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
    self.synced = (self.synced == False)
    if self.synced:
      self.sync_button.SetBitmapLabel(self.bmp['locked'])
      self.SetOffset(self._CalculateOffset())
      self.riff_slider.Disable()
      if self.db_file:
        self.save_offset_button.Enable()
    else:
      self.sync_button.SetBitmapLabel(self.bmp['unlocked'])
      self.riff_slider.Enable()

  def OnIdle(self, event):
    """Event handler for the Idle task.
    
    Used to update non-gui background processes
    """
    if not int(time.time()) % 10:
      self._ApplyOffset()

  def OnUpdateUI(self, event):
    """Event handler for the EVT_UPDATE_UI psuedo-signal."""
    self.offset_button.SetLabel('Offset: %s' % self.offset)
    if self.synced:
      self.sync_button.SetBitmapLabel(self.bmp['locked'])
      self.riff_slider.Disable()
    else:
      self.sync_button.SetBitmapLabel(self.bmp['unlocked'])
      self.riff_slider.Enable()
    try:
      vid_duration_milli = self.video.Length()
      vid_position_milli = self.video.Tell()
      riff_duration_milli = self.riff.Length()
      riff_position_milli = self.riff.Tell()
      self.video_timer.SetLabel(self._FormatTimestamp(vid_position_milli))
      self.video_slider.SetValue(vid_position_milli)
      self.riff_timer.SetLabel(self._FormatTimestamp(riff_position_milli))
      self.riff_slider.SetValue(riff_position_milli)
    except Exception, e:
      logging.error('Error encountered obtaining postion/duration: %s', e)
      return

  def OnAbout(self, event):
    info = wx.AboutDialogInfo()
    info.Name = 'pyRiffplayer, a syncing media player'
    info.Version = __version__
    info.Copyright = 'Copyright 2008, Jon Allie (jon@jonallie.com)'
    info.Description = """
    A media player capable of playing and synchonizing a second audio track, as well
    as saving and automatically loading synchronization info.
    """
    info.WebSite = ('http://github.com/ja30278/pyriffplayer', 'Source repository')
    info.Developers = ['Jon Allie (jon@jonallie.com)']
    info.License = GPL
    wx.AboutBox(info)
    
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
    """Event handler for manualy entered offset."""
    offset = None
    dlg = wx.NumberEntryDialog(self, 'Enter offset (in milliseconds)', 'Offset',
                               'Offset', self.offset, 0, 10800000)
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
    frame = RiffPlayerFrame(None, title='Riff Player')
    frame.SetDbFile(DEFAULT_DB_FILE)
    frame.Show(True)
    frame.Centre()

    return True

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  app = RiffPlayer(0)
  app.MainLoop()
    

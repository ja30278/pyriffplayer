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

class RiffPlayerFrame(wx.Frame):

  def __init__(self, parent, id, title):
    """Initialize the main riff player frame."""
    wx.Frame.__init__(self, parent, wx.ID_ANY, title, size = (550, 500))
    self.Bind(wx.EVT_CLOSE, self.Destroy)

    self.video_file = None
    self.riff_file = None
    self.synced = False
    self.offset = 0

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
    self.sync_button = wx.ToggleButton(self, -1, 'Sync')

    controls1.Add(self.video_select_button, 0, wx.ALL, 5)
    controls1.Add(self.video_slider, 1, wx.ALL|wx.EXPAND, 5)
    controls1.Add(self.video_timer, 0, wx.ALL, 5)
    controls2.Add(self.riff_select_button, 0, wx.ALL, 5)
    controls2.Add(self.riff_slider, 1, wx.ALL|wx.EXPAND, 5)
    controls2.Add(self.riff_timer, 0, wx.ALL, 5)
    controls3.Add(self.play_button, 0, wx.ALL, 5)
    controls3.Add(self.sync_button, 0, wx.ALL, 5)
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
    self.Bind(wx.EVT_SLIDER, self.OnVideoSliderUpdate, self.video_slider)
    self.Bind(wx.EVT_SLIDER, self.OnRiffSliderUpdate, self.riff_slider)

    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)

    # set up gstreamer pipeline
    self.player = gst.Pipeline('player')

    self.riff = gst.element_factory_make('playbin', 'riff-pbin')
    self.video = gst.element_factory_make('playbin', 'video-pbin')

    self.video_sink = gst.element_factory_make('autovideosink', 'video-sink')
    self.video.set_property('video-sink', self.video_sink)

    self.player.add(self.riff, self.video)
    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect('message', self.OnMessage)
    bus.connect('sync-message::element', self.OnSyncMessage)

    self._time_format = gst.FORMAT_TIME


  def OnPlayPause(self, event):
    """Event handler for play button events."""
    if not self.video_file or not self.riff_file:
      return
    state = self.play_button.GetLabel()
    if state == 'Play':
      self.player.set_state(gst.STATE_PLAYING)
      self.play_button.SetLabel('Pause')
    else:
      self.player.set_state(gst.STATE_PAUSED)
      self.play_button.SetLabel('Play')

  def OnVideoSliderUpdate(self, event):
    pos = self.video_slider.GetValue()
    pos *= 1000000000
    self.video.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, pos)
    if self.synced and self.offset != 0:
      riff_pos = pos + (self.offset * 1000000000)
      logging.debug('Sync: Seeking riff to: %s', riff_pos)
      self.riff.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, riff_pos)

  def OnRiffSliderUpdate(self, event):
    pos = self.riff_slider.GetValue()
    pos *= 1000000000
    self.riff.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, pos)
    if self.synced and self.offset != 0:
      video_pos = pos - (self.offset * 1000000000)
      logging.debug('Sync: Seeking video to: %s', video_pos)
      self.video.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, video_pos)

  def OnChooseRiff(self, event):
    """Event handler for riff selection."""
    self.riff_file = self._ChooseFile()
    self.riff.set_property('uri', 'file://%s' % self.riff_file)
    logging.debug('Riff file: %s', self.riff_file)
  
  def OnChooseVideo(self, event):
    """Event handler for video selection."""
    self.video_file = self._ChooseFile()
    self.video.set_property('uri', 'file://%s' % self.video_file)
    logging.debug('Video file: %s', self.video_file)

  def _CalculateOffset(self):
    offset = 0
    try:
      vid_position_nano, _ = self.video.query_position(gst.FORMAT_TIME)
      riff_position_nano, _ = self.riff.query_position(gst.FORMAT_TIME)
      offset = (riff_position_nano - vid_position_nano) / 1000000000
    except Exception, e:
      logging.error('Offset calculation error: %s', e)
    return offset

  def OnToggleSync(self, event):
    """Event handler for sync button."""
    self.synced = self.synced == False 
    self.offset = 0
    if not self.synced:
      return
    _, state, _ = self.player.get_state()
    if state == gst.STATE_PLAYING:
      self.offset = self._CalculateOffset()
      logging.debug('Set offset: %s', self.offset)

  def OnUpdateUI(self, event):
    """Event handler for the EVT_UPDATE_UI psuedo-signal."""
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
    
  def _ChooseFile(self, dirname='/'):
    """Utility function for selecting a file.
    
    Args:
      dirname: starting directory

    Returns:
      str - the full path to the selected file
    """
    filename = None
    dlg = wx.FileDialog(self, 'Choose a file', dirname, '', '*.*', wx.OPEN)
    if dlg.ShowModal() == wx.ID_OK:
      filename = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
    dlg.Destroy()
    return filename

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
    frame.Show(True)
    frame.Centre()
    return True

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  app = RiffPlayer(0)
  app.MainLoop()
    

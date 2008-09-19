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
__version__ = '.1'

import getopt
import sys
import time

from pyglet import app
from pyglet import event
from pyglet import media
from pyglet import resource
from pyglet import text
from pyglet import window

import db_lib
import gui_lib

resource.path.append('res')
resource.reindex()

def usage():
  print '%s -v [video] -r [riff] [-d riffdb]' % sys.argv[0]


class RiffPlayer(window.Window):
  CONTROL_PANEL_HEIGHT = 50
  SLIDER_HEIGHT = 20
  PADDING = 5
  BUTTON_WIDTH = 32
  LABEL_WIDTH = 48 

  def __init__(self, video, audio, offset=None):
    super(RiffPlayer, self).__init__(caption='RiffPlayer %s' % __version__,
                                     visible=False,
                                     resizable=True)
    self.video_player = video
    self.audio_player = audio
    self.synced = offset is not None 
    self.offset = offset
    self.video_player.push_handlers(self)
    self.audio_player.push_handlers(self)
    self.video_x = 0
    self.video_y = 0 + self.CONTROL_PANEL_HEIGHT
    self.overlay = None
    self.play_button = gui_lib.ImageButton(self,
                                           resource.image('play.png'),
                                           resource.image('play-active.png'))
    self.play_button.on_press = self.toggle_playback_all
    self.sync_button = gui_lib.ImageButton(self,
                                           resource.image('sync.png'),
                                           resource.image('sync-active.png'))
    self.sync_button.on_press = lambda: self.toggle_synced()
    self.play_button.set_pos(self.PADDING, self.PADDING)
    self.sync_button.set_pos(0 + self.BUTTON_WIDTH + self.PADDING * 2, self.PADDING)
    self.video_slider = gui_lib.Slider(self, self._get_slider_width()) 
    self.video_slider.set_pos(self.PADDING + (self.BUTTON_WIDTH + self.PADDING) * 4,
                              self.SLIDER_HEIGHT + self.PADDING)
    self.video_slider.on_begin_scroll = lambda: self.pause_all()
    self.video_slider.on_end_scroll = lambda: self.play_all()
    self.video_slider.on_change = self.video_seek 
    self.audio_slider = gui_lib.Slider(self, self._get_slider_width())
    self.audio_slider.set_pos(self.PADDING + (self.BUTTON_WIDTH + self.PADDING) * 4,
                              self.PADDING)
    self.audio_slider.on_begin_scroll = lambda: self.pause_all()
    self.audio_slider.on_end_scroll = lambda: self.play_all()
    self.audio_slider.on_change = self.audio_seek
    self.video_label = text.Label('VIDEO',
                                  font_name='Tahoma',
                                  font_size=10,
                                  bold=True,
                                  anchor_x = 'right',
                                  x=self.video_slider.x - self.PADDING,
                                  y=self.video_slider.y)
    self.audio_label = text.Label('RIFF',
                                  font_name='Tahoma',
                                  font_size=10,
                                  bold=True,
                                  anchor_x = 'right',
                                  x=self.audio_slider.x - self.PADDING,
                                  y=self.audio_slider.y)
    self.video_timer = text.Label('%3.2f' % (self.video_player.time/60,),
                                  font_name='Times New Roman',
                                  font_size=12,
                                  x=self.width - self.LABEL_WIDTH - self.PADDING,
                                  y=self.video_slider.y)
    self.audio_timer = text.Label('%3.2f' % (self.audio_player.time/60,),
                                  font_name='Times New Roman',
                                  font_size=12,
                                  x=self.width - self.LABEL_WIDTH - self.PADDING,
                                  y=self.audio_slider.y)
    self.controls = [self.play_button,
                     self.sync_button,
                     self.video_slider,
                     self.audio_slider]
    self.labels = [self.audio_label,
                   self.video_label,
                   self.video_timer,
                   self.audio_timer]

  def _get_slider_width(self):
    return(self.width - (self.BUTTON_WIDTH + self.PADDING) * 6) 

  def pause_all(self):
    self.video_player.pause()
    self.audio_player.pause()
    self.play_button.active = False

  def video_seek(self, value):
    self.video_player.seek(value)
    if self.synced and self.offset is not None:
      self.audio_player.seek(self.video_player.time + self.offset) 
    self.update_controls()

  def audio_seek(self, value):
    self.audio_player.seek(value)
    if self.synced and self.offset is not None:
      self.video_player.seek(self.audio_player.time - self.offset)
    self.update_controls()

  def play_all(self):
    self.video_player.play()
    self.audio_player.play()
    self.play_button.active = True

  def toggle_playback_all(self):
    if self.video_player.playing or self.audio_player.playing:
      self.pause_all()
    else:
      self.play_all()

  def toggle_synced(self):
    self.synced = self.synced is False
    if self.synced:
      self.offset = self.audio_player.time - self.video_player.time

  def get_video_size(self):
    if not self.video_player.source or not self.video_player.source.video_format:
      return 0, 0
    video_format = self.video_player.source.video_format
    width = video_format.width
    height = video_format.height
    if video_format.sample_aspect > 1:
      width *= video_format.sample_aspect
    elif video_format.sample_aspect < 1:
      height /= video_format.sample_aspect
    return width, height
    
  def set_default_video_size(self):
    self.set_size(*self.get_video_size())
    self.video_slider.max = self.video_player.source.duration
    self.audio_slider.max = self.audio_player.source.duration

  def on_resize(self, width, height):
    super(RiffPlayer, self).on_resize(width, height)
    video_width, video_height = self.get_video_size()
    if video_width == 0 or video_height == 0:
      return
    height -= self.CONTROL_PANEL_HEIGHT
    display_aspect = width / float(height)
    video_aspect = video_width / float(video_height)
    if video_aspect > display_aspect:
      self.video_width = width 
      self.video_height = width / video_aspect
    else:
      self.video_height = height
      self.video_width = height * video_aspect
    self.video_x = (width - self.video_width) / 2
    self.video_y = (height - self.video_height) / 2 + self.CONTROL_PANEL_HEIGHT
    self.video_slider.on_resize(self._get_slider_width())
    self.audio_slider.on_resize(self._get_slider_width())
    self.video_timer.x = self.width - self.LABEL_WIDTH - self.PADDING
    self.audio_timer.x = self.width - self.LABEL_WIDTH - self.PADDING

  def on_key_press(self, symbol, modifiers):
    if symbol == window.key.UP:
      self.video_player.volume = min(self.video_player.volume + .1, 1.0) 
      self.dispatch_event('on_video_volume_change')
    elif symbol == window.key.DOWN:
      self.video_player.volume = max(self.video_player.volume - .1, 0.0) 
      self.dispatch_event('on_video_volume_change')
    elif symbol == window.key.RIGHT:
      self.audio_player.volume = min(self.audio_player.volume + .1, 1.0)
      self.dispatch_event('on_audio_volume_change')
    elif symbol == window.key.LEFT:
      self.audio_player.volume = max(self.audio_player.volume - .1, 0.0) 
      self.dispatch_event('on_audio_volume_change')
    elif symbol == window.key.SPACE:
      self.toggle_playback_all()

  def on_mouse_press(self, x, y, button, modifiers):
    for control in self.controls:
      if control.hit_test(x, y):
        control.on_mouse_press(x, y, button, modifiers)

  def on_video_volume_change(self):
    label = gui_lib.centered_label(
        'Video Vol:%0.1f' %  self.video_player.volume,
         self.width,
         self.height)
    self.add_overlay(label, 2)

  def on_audio_volume_change(self):
    label = gui_lib.centered_label(
        'Riff Vol:%0.1f' % self.audio_player.volume,
        self.width,
        self.height)
    self.add_overlay(label, 2)

  def draw_media(self):
    self.video_player.get_texture().blit(self.video_x,
                                         self.video_y,
                                         width=self.video_width,
                                         height=self.video_height)

  def add_overlay(self, element, duration):
    self.overlay = (element, time.time() + duration)

  def draw_controls(self):
    self.update_controls()
    for control in self.controls:
      control.draw()

  def draw_labels(self):
    for label in self.labels:
      label.draw()

  def draw_overlay(self):
    if self.overlay is None:
      return
    overlay, expire  = self.overlay
    if time.time() < expire:
      overlay.draw()
  
  def update_controls(self):
    self.video_timer.text = '%3.2f' % (self.video_player.time/60,)
    self.audio_timer.text = '%3.2f' % (self.audio_player.time/60,)
    self.video_slider.value = self.video_player.time
    self.audio_slider.value = self.audio_player.time
    self.sync_button.active = self.synced
    self.play_button.active = self.video_player.playing or self.audio_player.playing

  def on_draw(self):
    self.clear()
    self.draw_media()
    self.draw_controls()
    self.draw_labels()
    self.draw_overlay()
    
RiffPlayer.register_event_type('on_video_volume_change')
RiffPlayer.register_event_type('on_audio_volume_change')

if __name__ == '__main__':

  try:
    opts, args = getopt.getopt(sys.argv[1:],
                               'hr:v:d:',
                                ['help', 'riff=', 'video=', 'database='])
  except getopt.GetoptError, e:
    print 'Option error: %s' % e
    usage()
    sys.exit(1)

  video_file = audio_file = riff_db = None

  for o,a in opts:
    if o in ('-h', '--help'):
      usage()
      sys.exit(0)
    elif o in ('-r', '--riff'):
      audio_file = a
    elif o in ('-v', '--video'):
      video_file = a
    elif o in ('-d', '--database'):
      riff_db = a

  if video_file is None or audio_file is None:
    usage()
    sys.exit(1)

  video = media.Player()
  riff = media.Player()

  video_stream = media.load(video_file)
  audio_stream = media.load(audio_file)

  video.queue(video_stream)
  riff.queue(audio_stream)
  video.volume = 0.9
  riff.volume = 1.0

  offset = None
  if riff_db is not None:
    db = db_lib.RiffDatabase(riff_db)
    offset = db.get_offset(video_file, audio_file)
    
  player = RiffPlayer(video, riff, offset)
  player.set_default_video_size()


    
  player.set_visible(True)

  app.run()

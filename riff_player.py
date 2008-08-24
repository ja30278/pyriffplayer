#!/usr/bin/env python

__author__ = 'Jon Allie (jon@jonallie.com)'
__version__ = '.1'

import sys

from pyglet import app
from pyglet import event
from pyglet import image
from pyglet import media
from pyglet import resource
from pyglet import window

_RESOURCE_PATHS = ['resources']

class Control(event.EventDispatcher):

  def __init__(self, parent):
    super(Control, self).__init__()
    self.parent = parent

  def hit_test(self, x, y):
    return (self.x < x < self.x + self.width and
            self.y < y < self.y + self.height)

  def capture_events(self):
    self.parent.push_handlers(self)

  def release_events(self):
    self.parent.remove_handlers(self)

  def set_pos(self, x, y):
    self.x = x
    self.y = y


class ImageButton(Control):

  def __init__(self, parent, image, active_image=None):
    """Initialize the image button.

    Args:
      parent: parent element
      image: image resource.
    """
    super(ImageButton, self).__init__(parent)
    self.image = image
    self.active_image = active_image
    self.width = self.image.width
    self.height = self.image.height 
    self.active = False

  def draw(self):
    if self.active and self.active_image:
      image = self.active_image
    else:
      image = self.image
    image.blit(self.x, self.y)

  def on_mouse_press(self, x, y, button, modifiers):
    self.capture_events()

  def on_mouse_release(self, x, y, button, modifiers):
    self.release_events()
    if self.hit_test(x, y):
      self.active = self.active is False 
      self.dispatch_event('on_press')

ImageButton.register_event_type('on_press') 
  

class Slider(Control):

  TRACK_COLOR = (50,50,50,255)
  
  def __init__(self, parent, width, min_val=0, max_val=0):
    super(Slider, self).__init__(parent)
    self.x = 0
    self.y = 0
    self.min = min_val 
    self.max = max_val 
    self.width = width
    self.handle = resource.image('slider.png')
    self.height = self.handle.height 
    self.track = image.SolidColorImagePattern(
        Slider.TRACK_COLOR).create_image(self.width, self.height)
    self.value = min_val 

  def coordinate_to_value(self, x):
    return float(x - self.x) / self.width * (self.max - self.min) + self.min

  def value_to_coordinate(self, value):
    return float(value - self.min) / (self.max - self.min) * self.width + self.x
  
  def draw(self):
    self.track.blit(self.x, self.y)
    self.handle.blit(self.value_to_coordinate(self.value), self.y)

  def on_resize(self, width):
    self.width = width
    self.track = image.SolidColorImagePattern(
      Slider.TRACK_COLOR).create_image(self.width, self.height)

  def on_mouse_press(self, x, y, button, modifiers):
    self.value = self.coordinate_to_value(x)
    self.capture_events()
    self.dispatch_event('on_begin_scroll')
    self.dispatch_event('on_change', self.value)

  def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
   value = min(max(self.coordinate_to_value(x), self.min), self.max)
   self.dispatch_event('on_change', value)

  def on_mouse_release(self, x, y, button, modifiers):
    self.release_events()
    self.dispatch_event('on_end_scroll')

Slider.register_event_type('on_begin_scroll')
Slider.register_event_type('on_end_scroll')
Slider.register_event_type('on_change')
Slider.register_event_type('on_resize')
    
    

class RiffPlayer(window.Window):
  CONTROL_PANEL_HEIGHT = 40
  SLIDER_HEIGHT = 10
  PADDING = 5
  BUTTON_WIDTH = 43

  def __init__(self, video, audio):
    super(RiffPlayer, self).__init__(caption='RiffPlayer %s' % __version__,
                                     visible=False,
                                     resizable=True)
    self.video_player = video
    self.audio_player = audio
    self.synced = False
    self.video_player.push_handlers(self)
    self.audio_player.push_handlers(self)
    self.video_x = 0
    self.video_y = 0 + self.CONTROL_PANEL_HEIGHT
    self.play_button = ImageButton(self,
                                   resource.image('play.png'),
                                   resource.image('play-active.png'))
    self.play_button.on_press = self.toggle_playback_all
    self.sync_button = ImageButton(self,
                                   resource.image('sync.png'),
                                   resource.image('sync-active.png'))
    self.sync_button.on_press = lambda: self.toggle_synced()
    self.play_button.set_pos(0,0)
    self.sync_button.set_pos(0 + self.BUTTON_WIDTH + self.PADDING, 0)
    self.video_slider = Slider(self, self.width - self.BUTTON_WIDTH * 2)
    self.video_slider.set_pos(0 + (self.BUTTON_WIDTH + self.PADDING) * 2,
                              self.SLIDER_HEIGHT + self.PADDING)
    self.video_slider.on_begin_scroll = lambda: self.pause_all()
    self.video_slider.on_end_scroll = lambda: self.play_all()
    self.video_slider.on_change = lambda value: self.seek(self.video_player,
                                                          self.audio_player,
                                                          value)
    self.audio_slider = Slider(self, self.width - self.BUTTON_WIDTH * 2)
    self.audio_slider.set_pos(0 + (self.BUTTON_WIDTH + self.PADDING) * 2,
                              self.PADDING)
    self.audio_slider.on_begin_scroll = lambda: self.pause_all()
    self.audio_slider.on_end_scroll = lambda: self.play_all()
    self.audio_slider.on_change = lambda value: self.seek(self.audio_player,
                                                          self.video_player,
                                                          value)
    self.controls = [self.play_button,
                     self.sync_button,
                     self.video_slider,
                     self.audio_slider]

  def pause_all(self):
    self.video_player.pause()
    self.audio_player.pause()
    self.play_button.active = False
  
  def play_all(self):
    self.video_player.play()
    self.audio_player.play()
    self.play_button.active = True

  def seek(self, player, sync_player, value):
    if self.synced:
      offset = value - player.time
      sync_player.seek(sync_player.time + offset)
    player.seek(value)
    self.update_controls()
       
  def toggle_playback_all(self):
    if self.video_player.playing or self.audio_player.playing:
      self.pause_all()
    else:
      self.play_all()

  def toggle_synced(self):
    self.synced = self.synced is False

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
    self.video_width = width 
    self.video_height = height - self.CONTROL_PANEL_HEIGHT
    slider_width = width - (self.BUTTON_WIDTH + self.PADDING) * 2
    self.video_slider.on_resize(slider_width)
    self.audio_slider.on_resize(slider_width)

  def on_mouse_press(self, x, y, button, modifiers):
    for control in self.controls:
      if control.hit_test(x, y):
        control.on_mouse_press(x, y, button, modifiers)

  def draw_media(self):
    self.video_player.get_texture().blit(self.video_x,
                                         self.video_y,
                                         width=self.video_width,
                                         height=self.video_height)

  def draw_controls(self):
    for control in self.controls:
      control.draw()

  def update_controls(self):
    self.video_slider.value = self.video_player.time
    self.audio_slider.value = self.audio_player.time

  def on_draw(self):
    self.draw_media()
    self.draw_controls()
    

if __name__ == '__main__':

  if len(sys.argv) < 3:
    print 'Usage: riff_player.py <video> <riff>'
    sys.exit(1)

  video = media.Player()
  riff = media.Player()
  player = RiffPlayer(video, riff)

  video_stream = media.load(sys.argv[1])
  audio_stream = media.load(sys.argv[2])

  video.queue(video_stream)
  riff.queue(audio_stream)
  
  video.volume = 0.5
  riff.volume = 1.0
  player.set_default_video_size()
  player.set_visible(True)

  app.run()
                          

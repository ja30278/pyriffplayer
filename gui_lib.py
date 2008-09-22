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

from pyglet import event
from pyglet import image
from pyglet import resource
from pyglet import text

def centered_label(label_text, width, height):
  return text.Label(label_text,
                    font_name='Times New Roman',
                    font_size=36,
                    x=width//2, y=height//2,
                    anchor_x='center', anchor_y='center')

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

  def set_pos(self, x=None, y=None):
    self.x = x or self.x
    self.y = y or self.y


class Button(Control):
  
  def on_mouse_press(self, x, y, button, modifiers):
    self.capture_events()

Button.register_event_type('on_press')

class TextButton(Button):
  PADDING = 5
  
  def __init__(self, parent, button_text, font_name='Times New Roman',
               font_size=12):
    super(TextButton, self).__init__(parent)
    self.label = text.Label(button_text,
                            font_name=font_name,
                            font_size=font_size,
                            anchor_x='center',
                            anchor_y='center')
    self.width = self.label.content_width + self.PADDING
    self.height = self.label.content_height + self.PADDING

  def draw(self):
    self.label.draw()

  def set_text(self, text):
    self.label.text = text
    self.width = self.label.content_width + self.PADDING
    self.height = self.label.content_height + self.PADDING

  def set_pos(self, x=None, y=None):
    self.x = x or self.x
    self.y = y or self.y
    self.label.x = self.x
    self.label.y = self.y

  def on_mouse_release(self, x, y, button, modifiers):
    self.release_events()
    if self.hit_test(x, y):
      self.dispatch_event('on_press')

  
class ImageButton(Button):

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
    return max(0, min(float(value - self.min) / (self.max - self.min) * self.width + self.x, self.max))
  
  def draw(self):
    self.track.blit(self.x, self.y)
    self.handle.blit(self.value_to_coordinate(self.value), self.y)

  def on_resize(self, width):
    self.width = width
    self.track = image.SolidColorImagePattern(
      Slider.TRACK_COLOR).create_image(self.width, self.height)

  def on_mouse_press(self, x, y, button, modifiers):
    value = self.coordinate_to_value(x)
    self.capture_events()
    self.dispatch_event('on_begin_scroll')
    self.dispatch_event('on_change', value)

  def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
   value = min(max(self.coordinate_to_value(x), self.min), self.max)
   self.dispatch_event('on_change', value)

  def on_mouse_release(self, x, y, button, modifiers):
    value = self.coordinate_to_value(x)
    self.release_events()
    self.dispatch_event('on_change', value)
    self.dispatch_event('on_end_scroll')

Slider.register_event_type('on_begin_scroll')
Slider.register_event_type('on_end_scroll')
Slider.register_event_type('on_change')
Slider.register_event_type('on_resize')

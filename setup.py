"""
py2app setup file for the openriff player.
"""

import glob
import sys

from setuptools import setup

if sys.platform == 'darwin':
  import py2app
  extra_options = dict(
    setup_requires=['py2app'], 
      options=dict(
        package_data=dict(
          res=['res/*']),
        py2app=dict(
          iconfile='res/riffplayer.icns',
          packages='wx',
          site_packages=True,
          plist=dict(
            CFBundleName='OpenRiff Player',
            CFBundleShortVersionString='0.1.1',
            CFBundleGetInfoString='OpenRiff Player 0.1.1',
            CFBundleExecutable='OpenRiff Player',
            CFBundleIdentifier='com.openriff.player',
          ),
        ),
      ),
  )
elif sys.platform == 'win32':
  import py2exe
  extra_options = dict(
      setup_requires=['py2exe'],
      data_files=[
        ('res',
          glob.glob('res\\*'))],
      options=dict(
        py2exe=dict(
          compressed=1,
          optimize=2,
          bundle_files=1
        )
      ),
      windows=[
        dict(
          script='riffplayer.py',
          icon_resources=[(2, 'res/riffplayer.ico')])
          ]
  )
else:
  # untested
  extra_options = dict(
    scripts=['riffplayer.py']
  )

setup(
  name=['Openriff Player'],
  app=['riffplayer.py'],
  **extra_options
)

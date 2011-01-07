"""
py2app setup file for the openriff player.
"""

import py2app
from setuptools import setup

setup(
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
  app=['riffplayer.py'],
)





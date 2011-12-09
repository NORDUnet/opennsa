import time
gmt = time.gmtime()

# set this to "correct" version when making a release
__version__ = 'git-%04d%02d%02d' % (gmt.tm_year, gmt.tm_mon, gmt.tm_mday)


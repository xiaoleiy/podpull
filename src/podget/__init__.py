"""podget — download specific podcast episode audio, reliably.

Apple Podcasts is a directory that holds no audio; it points at each show's
RSS feed, where every episode carries a direct <enclosure> audio URL. podget
walks that chain (Apple/RSS/xiaoyuzhou link -> feed -> enclosure) and downloads
the file. Stdlib only.
"""

__version__ = "0.1.0"

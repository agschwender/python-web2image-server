#!/usr/bin/env python

import logging
import signal
import sys

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import *
from PyQt4.QtWebKit import *

import web2imageserver.httpdaemon

def main():
    app = QApplication(sys.argv)
    logging.getLogger().setLevel(logging.DEBUG)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    logging.info("starting web2image server")
    daemon = web2imageserver.httpdaemon.HttpDaemon(8888, app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

import logging
import urlparse

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import *
from PyQt4.QtWebKit import *

class HttpSocket(QTcpSocket):
    def __init__(self, parent=None, **kwargs):
        super(HttpSocket, self).__init__(parent)
        self._http_proxy_url = kwargs.get("http_proxy_url", None)
        self._network_manager = None
        self._thumbnail_scale = kwargs.get("thumbnail_scale", 0.5)
        self._timeout = kwargs.get("timeout", 15)
        self._url_parameter = kwargs.get("url_parameter", "url")
        self._viewport_size = kwargs.get("viewport_size", (1000, 800))
        if self._http_proxy_url:
            http_proxy_url = QUrl(self._http_proxy_url)
            if unicode(self._http_proxy_url.scheme()).startswith('http'):
                protocol = QNetworkProxy.HttpProxy
            else:
                protocol = QNetworkProxy.Socks5Proxy
            proxy = QNetworkProxy(protocol,
                                  http_proxy_url.host(),
                                  http_proxy_url.port(),
                                  http_proxy_url.userName(),
                                  http_proxy_url.password())
            self._network_manager = QNetworkAccessManager()
            self._network_manager.setProxy(proxy)

    def readClient(self):
        try:
            self.url = self._prepare_url(self._parse_url())
            if self.url:
                logging.debug("requesting %s" % self.url)
                self._load_and_render_page()
                return
            self._http_404()
        except Exception, e:
            logging.warning(e)
            self._http_500()

    def discardClient(self):
        self.deleteLater()

    def _http_200(self, content):
        os = QTextStream(self)
        os.setAutoDetectUnicode(True)
        os << "HTTP/1.0 200 Ok\r\nContent-Type: image/jpeg\r\n\r\n"
        os = QDataStream(self)
        os.writeRawData(content)
        self.close()

    def _http_404(self):
        os = QTextStream(self)
        os.setAutoDetectUnicode(True)
        os << "HTTP/1.0 404 Not Found\r\n" \
           + "Content-Type: text/html; charset=\"utf-8\"\r\n" \
           + "\r\n" \
           + "<h1>Not found</h1>\n"
        self.close()

    def _http_500(self):
        os = QTextStream(self)
        os.setAutoDetectUnicode(True)
        os << "HTTP/1.0 500 Internal Error\r\n" \
           + "Content-Type: text/html; charset=\"utf-8\"\r\n" \
           + "\r\n" \
           + "<h1>Unable to process your request</h1>\n"
        self.close()

    def _parse_url(self):
        if not self.canReadLine():
            return None
        tokens = QString(self.readLine()).split(
            QRegExp("[ \r\n][ \r\n]*"))
        if len(tokens) < 2 or tokens[0] != "GET" or not tokens[1]:
            return None
        o = urlparse.urlsplit(str(tokens[1]))
        if not o.query:
            return None
        d = urlparse.parse_qs(o.query)
        if not self._url_parameter in d or not d[self._url_parameter]:
            return None
        return d[self._url_parameter][0]

    def _prepare_url(self, url):
        if not url:
            return None
        elif not url.startswith("http"):
            url = "http://" + url
        return url

    def _load_and_render_page(self):
        self.page = QWebPage()
        self.page.setViewportSize(QSize(self._viewport_size[0],
                                        self._viewport_size[1]))
        if self._network_manager:
            self.page.setNetworkAccessManager(self._network_manager)
        self.page.connect(
            self.page, SIGNAL("loadStarted()"), self._onLoadStarted)
        self.page.connect(
            self.page, SIGNAL("loadFinished(bool)"), self._onLoadFinished)
        self.page.mainFrame().setScrollBarPolicy(
            Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        self.page.mainFrame().setScrollBarPolicy(
            Qt.Vertical, Qt.ScrollBarAlwaysOff)
        req = QNetworkRequest()
        self.page.mainFrame().load(QUrl(self.url))

    def _render_page(self):
        image = QImage(self.page.viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.page.mainFrame().render(painter)
        painter.end()
        image = image.scaledToWidth(
            int(float(self._thumbnail_scale) * float(self._viewport_size[0])),
            Qt.SmoothTransformation)
        buf = QBuffer()
        image.save(buf, "jpg")
        return buf

    def _process_output(self, buf):
        return buf

    def _onLoadStarted(self):
        self._is_loading = True
        if self._timeout:
            self.timer = QTimer()
            self.timer.connect(
                self.timer, SIGNAL("timeout()"), self._onLoadTimeout)
            self.timer.start(self._timeout * 1000)

    def _onLoadTimeout(self):
        self.page.disconnect(
            self.page, SIGNAL("loadFinished"), self._onLoadFinished)
        self.timer.stop()
        logging.info("request timeout for %s" % self.url)
        self._http_500()

    def _onLoadFinished(self, result):
        self.timer.disconnect(
            self.timer, SIGNAL("timeout()"), self._onLoadTimeout)
        if not result:
            return self._http_404()
        try:
            buf = self._process_output(self._render_page())
            self._http_200(buf.buffer().data())
        except Exception, e:
            logging.warning(e)
            self._http_500()


class HttpDaemon(QTcpServer):
    def __init__(self, port, parent=None, **kwargs):
        super(HttpDaemon, self).__init__(parent)
        self.listen(QHostAddress.Any, port)
        self._passthru_kwargs = kwargs

    def incomingConnection(self, socket):
        s = HttpSocket(self, **self._passthru_kwargs)
        self.connect(s, SIGNAL("readyRead()"), s.readClient)
        self.connect(s, SIGNAL("disconnected()"), s.discardClient)
        s.setSocketDescriptor(socket)
        logging.debug("new connection")

import json
import threading

import websocket

from config import BINANCE_WS_BASE


class BinanceKlineStream:
    def __init__(self, streams, on_message_callback):
        self.streams = streams
        self.on_message_callback = on_message_callback
        self.ws = None
        self.thread = None

    def _build_url(self):
        return BINANCE_WS_BASE + "/".join(self.streams)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            self.on_message_callback(data)
        except Exception:
            pass

    def _on_error(self, ws, error):
        print("WS HATA:", error)

    def _on_close(self, ws, close_status_code, close_msg):
        print("WS kapandı:", close_status_code, close_msg)

    def _on_open(self, ws):
        print("WS bağlandı")

    def start(self):
        self.ws = websocket.WebSocketApp(
            self._build_url(),
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.ws:
            self.ws.close()

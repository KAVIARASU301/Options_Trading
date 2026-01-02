# core/market_data_worker.py - COMPLETE FIXED VERSION

import logging
from typing import Set, Optional
from PySide6.QtCore import QObject, Signal, QTimer
from kiteconnect import KiteTicker
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MarketDataWorker(QObject):
    """
    Manages the KiteTicker WebSocket connection from the main thread.
    The KiteTicker itself runs in a background thread.
    """
    data_received = Signal(list)
    connection_closed = Signal()
    connection_error = Signal(str)
    connection_status_changed = Signal(str)

    def __init__(self, api_key: str, access_token: str):
        super().__init__()
        self.api_key = api_key
        self.access_token = access_token
        self.kws: Optional[KiteTicker] = None
        self.is_running = False
        self.subscribed_tokens: Set[int] = set()
        self.reconnect_attempts = 0
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self.reconnect)
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self._check_heartbeat)
        self.last_tick_time: Optional[datetime] = None

    def start(self):
        """Initializes and connects the KiteTicker WebSocket client."""
        if self.is_running:
            logger.warning("MarketDataWorker is already running.")
            return

        logger.info("MarketDataWorker starting...")
        self.connection_status_changed.emit("Connecting")
        self.kws = KiteTicker(self.api_key, self.access_token)

        # Assign callbacks
        self.kws.on_ticks = self._on_ticks
        self.kws.on_connect = self._on_connect
        self.kws.on_close = self._on_close
        self.kws.on_error = self._on_error

        # The connect call is non-blocking and runs in its own thread
        self.kws.connect(threaded=True)
        self.is_running = True

    def _check_heartbeat(self):
        if self.is_running and self.last_tick_time:
            if datetime.now() - self.last_tick_time > timedelta(seconds=30):
                logger.warning("Heartbeat: No ticks received in the last 30 seconds. Assuming disconnection.")
                if self.kws:
                    self.kws.stop()
                self._on_close(self.kws, 1001, "Heartbeat Timeout")

    def _on_ticks(self, _, ticks):
        """Callback for receiving ticks."""
        self.last_tick_time = datetime.now()
        self.data_received.emit(ticks)

    def _on_connect(self, _, response):
        """Callback on successful connection."""
        logger.info("WebSocket connected. Subscribing to existing tokens.")
        self.connection_status_changed.emit("Connected")
        self.reconnect_attempts = 0
        self.last_tick_time = datetime.now()
        self.reconnect_timer.stop()
        QTimer.singleShot(0, lambda: self.heartbeat_timer.start(15000))

        # 🔥 FIX: Subscribe to any queued tokens
        if self.subscribed_tokens:
            token_list = list(self.subscribed_tokens)
            try:
                self.kws.subscribe(token_list)
                self.kws.set_mode(self.kws.MODE_FULL, token_list)
                logger.info(f"Subscribed to {len(token_list)} tokens on connect.")
            except Exception as e:
                logger.error(f"Failed to subscribe on connect: {e}")

    def _on_close(self, _, code, reason):
        """Callback on connection close."""
        logger.warning(f"WebSocket connection closed. Code: {code}, Reason: {reason}")
        self.is_running = False
        self.heartbeat_timer.stop()
        self.connection_status_changed.emit("Disconnected")
        self.connection_closed.emit()
        if not self.reconnect_timer.isActive():
            QTimer.singleShot(0, lambda: self.reconnect_timer.start(5000))

    def _on_error(self, _, code, reason):
        """Callback for WebSocket errors."""
        logger.error(f"WebSocket error. Code: {code}, Reason: {reason}")
        self.connection_status_changed.emit(f"Error: {reason}")
        self.connection_error.emit(str(reason))

    def reconnect(self):
        if not self.is_running:
            self.reconnect_attempts += 1
            logger.info(f"Attempting to reconnect... (Attempt #{self.reconnect_attempts})")
            self.connection_status_changed.emit(f"Reconnecting ({self.reconnect_attempts})...")
            self.start()

    def set_instruments(self, instrument_tokens: Set[int], append: bool = False):
        """
        🔥 FIXED: Updates or appends instrument tokens for subscription.
        """
        # Convert to set
        instrument_tokens_set = set(instrument_tokens)

        logger.debug(f"[set_instruments] Called with {len(instrument_tokens_set)} tokens, append={append}")

        if append:
            instrument_tokens_set |= self.subscribed_tokens

        # 🔥 CRITICAL: Check WebSocket connection state
        if not self.kws:
            logger.warning("[set_instruments] KiteTicker not initialized. Storing tokens.")
            self.subscribed_tokens = instrument_tokens_set
            return

        if not self.kws.is_connected():
            logger.warning("[set_instruments] WebSocket not connected. Storing tokens for later.")
            self.subscribed_tokens = instrument_tokens_set
            return

        # Calculate changes
        new_tokens = instrument_tokens_set
        old_tokens = self.subscribed_tokens

        tokens_to_add = list(new_tokens - old_tokens)
        tokens_to_remove = list(old_tokens - new_tokens) if not append else []

        # 🔥 FIX: Subscribe to new tokens
        if tokens_to_add:
            try:
                self.kws.subscribe(tokens_to_add)
                self.kws.set_mode(self.kws.MODE_FULL, tokens_to_add)
                logger.info(f"Subscribed to {len(tokens_to_add)} new tokens.")
            except Exception as e:
                logger.error(f"Failed to subscribe to new tokens: {e}")
                # Don't add to subscribed_tokens if subscription failed
                return

        # 🔥 FIX: Unsubscribe from removed tokens
        if tokens_to_remove:
            try:
                self.kws.unsubscribe(tokens_to_remove)
                logger.info(f"Unsubscribed from {len(tokens_to_remove)} tokens.")
            except Exception as e:
                logger.error(f"Failed to unsubscribe tokens: {e}")

        # 🔥 CRITICAL: Update internal state AFTER successful operations
        self.subscribed_tokens = new_tokens

        logger.debug(f"[set_instruments] Now tracking {len(self.subscribed_tokens)} tokens")

    def stop(self):
        """Stops the worker and closes the WebSocket connection."""
        logger.info("Stopping MarketDataWorker...")
        self.reconnect_timer.stop()
        self.heartbeat_timer.stop()
        if self.kws and self.is_running:
            self.kws.stop()
        self.is_running = False
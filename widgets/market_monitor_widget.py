import logging
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QPicture, QPainter

logger = logging.getLogger(__name__)


class CandlestickItem(pg.GraphicsObject):
    """
    Custom graphics object for efficient and professional-looking candlestick drawing.
    Features:
    - Anti-aliasing for smooth rendering.
    - Solid-filled bodies for both bullish and bearish candles.
    - Increased spacing between candles for clarity.
    """

    def __init__(self, data=None):
        super().__init__()
        self.data = data or []  # list of (x, open, high, low, close)
        self.generatePicture()

    def setData(self, data):
        """Update data and redraw picture."""
        self.data = data
        # --- FIX: Explicitly notify pyqtgraph that the item's geometry will change ---
        # This is the most reliable way to ensure a repaint for custom graphics items.
        self.prepareGeometryChange()
        self.generatePicture()

    def generatePicture(self):
        """
        Render all candles into a QPicture buffer for high performance.
        This version uses solid-filled candles and increased spacing.
        """
        pic = QPicture()
        painter = QPainter(pic)
        painter.setRenderHint(QPainter.Antialiasing)

        BULL_COLOR = '#26A69A'
        BEAR_COLOR = '#EF5350'
        w = 0.3

        for x, open_, high, low, close in self.data:
            bullish = close >= open_
            pen_color = BULL_COLOR if bullish else BEAR_COLOR
            pen = pg.mkPen(color=pen_color, width=1.5)
            painter.setPen(pen)
            painter.drawLine(x, low, x, high)

            brush_color = BULL_COLOR if bullish else BEAR_COLOR
            painter.setBrush(pg.mkBrush(brush_color))

            top = max(open_, close)
            bottom = min(open_, close)
            height = top - bottom
            if height == 0:
                height = 0.5

            painter.drawRect(QRectF(x - w, bottom, w * 2, height))

        painter.end()
        self.picture = pic

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if not self.data:
            return QRectF()
        xs, opens, highs, lows, closes = zip(*self.data)
        pen_width_offset = 1
        return QRectF(
            min(xs) - pen_width_offset,
            min(lows),
            (max(xs) - min(xs)) + (2 * pen_width_offset),
            max(highs) - min(lows)
        )


class MarketChartWidget(QWidget):
    """
    A widget to display market data for a single instrument using pyqtgraph,
    supporting candlesticks, a two-day view, zooming, and a CPR indicator.
    Efficient updates use a single CandlestickItem.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = ""
        self.chart_data = pd.DataFrame()
        self.chart_mode = 'candlestick'
        self.day_separator_pos = None
        self.cpr_levels = None
        self._candlestick_item = None
        self._line_plot = None

        self._setup_ui()
        self._setup_chart()
        self.show_message("EMPTY", "Awaiting symbol selection")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 2, 5, 2)
        self.symbol_label = QLabel("NO SYMBOL")
        self.symbol_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #E0E0E0;")
        header_layout.addWidget(self.symbol_label)
        header_layout.addStretch()
        button_style = ("QPushButton { font-size: 11px; background-color: #424242;"
                        " border-radius: 4px; color: white; padding: 4px 8px; }"
                        " QPushButton:hover { background-color: #555555; }")
        self.mode_btn = QPushButton("Line")
        self.mode_btn.setFixedWidth(60)
        self.mode_btn.setToolTip("Toggle Candlestick / Line View")
        self.mode_btn.setStyleSheet(button_style)
        self.mode_btn.clicked.connect(self.toggle_chart_mode)
        header_layout.addWidget(self.mode_btn)
        layout.addLayout(header_layout)
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)

    def _setup_chart(self):
        self.plot_widget.setBackground('#1A1A1A')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.setClipToView(True)
        self.plot_widget.setDownsampling(auto=True, mode='peak')
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.enableAutoRange(axis='y', enable=True)
        axis_pen = pg.mkPen(color='#B0B0B0', width=1)
        font = QFont("Segoe UI", 8)
        self.plot_widget.showAxis('right', True)
        for axis in [self.plot_widget.getAxis('left'), self.plot_widget.getAxis('right'),
                     self.plot_widget.getAxis('bottom')]:
            axis.setPen(axis_pen)
            axis.setTickFont(font)
        self.plot_widget.getAxis('bottom').setStyle(showValues=False)

    def set_data(self, symbol: str, data: pd.DataFrame, day_separator_pos: int | None = None,
                 cpr_levels: Dict | None = None):
        if data.empty:
            self.show_message(f"[{symbol}]", "No historical data available.")
            return
        self.symbol = symbol
        self.chart_data = data.copy()
        self.day_separator_pos = day_separator_pos
        self.cpr_levels = cpr_levels
        self.symbol_label.setText(self.symbol)
        self._plot_chart_data(full_redraw=True)
        self.set_visible_range("Auto")

    def _draw_cpr(self):
        if not self.cpr_levels:
            return
        if 'tc' in self.cpr_levels and 'bc' in self.cpr_levels:
            cpr_region = pg.LinearRegionItem(values=[self.cpr_levels['bc'], self.cpr_levels['tc']],
                                             orientation='horizontal', brush=pg.mkBrush(color=(0, 116, 217, 25)),
                                             pen=pg.mkPen(color=(0, 116, 217, 0)), movable=False)
            self.plot_widget.addItem(cpr_region)
        if 'pivot' in self.cpr_levels:
            pivot_line = pg.InfiniteLine(pos=self.cpr_levels['pivot'], angle=0, movable=False,
                                         pen=pg.mkPen(color='#F39C12', style=Qt.DotLine, width=1.5))
            self.plot_widget.addItem(pivot_line)

    def _plot_chart_data(self, full_redraw=False):
        if full_redraw:
            self.plot_widget.clear()
            self._draw_cpr()
            if self.day_separator_pos is not None:
                sep = pg.InfiniteLine(pos=self.day_separator_pos - 0.5, angle=90,
                                      pen=pg.mkPen(color='#3A4458', style=Qt.DashLine, width=1.5))
                self.plot_widget.addItem(sep)

        if self.chart_data.empty:
            return

        x_coords = np.arange(len(self.chart_data))

        if self.chart_mode == 'line':
            if self._line_plot and not full_redraw:
                self._line_plot.setData(x_coords, self.chart_data['close'].values)
            else:
                if self._candlestick_item: self.plot_widget.removeItem(
                    self._candlestick_item); self._candlestick_item = None
                if self._line_plot: self.plot_widget.removeItem(self._line_plot)
                self._line_plot = self.plot_widget.plot(x_coords, self.chart_data['close'].values,
                                                        pen=pg.mkPen(width=1.5))
        else:
            cs_data = list(zip(x_coords, self.chart_data['open'], self.chart_data['high'],
                               self.chart_data['low'], self.chart_data['close']))
            if self._candlestick_item is None or full_redraw:
                if self._line_plot: self.plot_widget.removeItem(self._line_plot); self._line_plot = None
                if self._candlestick_item: self.plot_widget.removeItem(self._candlestick_item)
                self._candlestick_item = CandlestickItem(cs_data)
                self.plot_widget.addItem(self._candlestick_item)
            else:
                self._candlestick_item.setData(cs_data)

    def add_tick(self, tick: dict):
        ltp = tick.get('last_price')
        if self.chart_data.empty or ltp is None:
            return

        parent_widget = self.parent()
        tf_str = "1min"
        if parent_widget and hasattr(parent_widget, 'timeframe_combo'):
            tf_str = parent_widget.timeframe_combo.currentText()

        now = datetime.now().replace(second=0, microsecond=0)
        tf_minutes = int(tf_str.replace("min", ""))
        rounded = now - timedelta(minutes=now.minute % tf_minutes)

        if rounded in self.chart_data.index:
            # --- PATH 1: Update current candle (high frequency) ---
            self.chart_data.at[rounded, 'close'] = ltp
            self.chart_data.at[rounded, 'high'] = max(self.chart_data.at[rounded, 'high'], ltp)
            self.chart_data.at[rounded, 'low'] = min(self.chart_data.at[rounded, 'low'], ltp)
            # Trigger a partial, inexpensive redraw.
            self._plot_chart_data(full_redraw=False)
        else:
            # --- PATH 2: Create a new candle (low frequency) ---
            last_close = self.chart_data.iloc[-1]['close']
            new_row = pd.DataFrame([{'open': last_close, 'high': ltp, 'low': ltp, 'close': ltp}],
                                   index=[rounded])
            self.chart_data = pd.concat([self.chart_data, new_row])
            self.chart_data.sort_index(inplace=True)
            # Trigger a full, robust redraw.
            self._plot_chart_data(full_redraw=True)
            if parent_widget and hasattr(parent_widget, 'candle_count_combo'):
                self.set_visible_range(parent_widget.candle_count_combo.currentText())

    def set_visible_range(self, count_str: str):
        if self.chart_data.empty: return
        vb = self.plot_widget.getViewBox()
        if count_str.lower() == 'auto':
            vb.enableAutoRange(axis=pg.ViewBox.XAxis)
        else:
            try:
                count = int(count_str)
                total = len(self.chart_data)
                start = max(0, total - count)
                vb.setXRange(start, total, padding=0.02)
            except Exception:
                vb.enableAutoRange(axis=pg.ViewBox.XAxis)

    def toggle_chart_mode(self):
        self.chart_mode = 'line' if self.chart_mode == 'candlestick' else 'candlestick'
        self.mode_btn.setText("Candle" if self.chart_mode == 'line' else "Line")
        self._plot_chart_data(full_redraw=True)
        if self.parent() and hasattr(self.parent(), 'candle_count_combo'):
            self.set_visible_range(self.parent().candle_count_combo.currentText())

    def show_message(self, title: str, message: str = ""):
        self.plot_widget.clear()
        self.symbol_label.setText(title)
        if message:
            text = pg.TextItem(message, color='#888888', anchor=(0.5, 0.5))
            text.setFont(QFont("Segoe UI", 10))
            self.plot_widget.addItem(text, ignoreBounds=True)
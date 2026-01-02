import pyqtgraph as pg
import pandas as pd
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt, QTimer

from core.cvd.cvd_historical import CVDHistoricalBuilder


class CVDChartWidget(QWidget):
    """
    CVD Chart Widget (Market Monitor / Dashboard Style)

    • Historical minute candles only
    • Refreshes every 3 seconds
    • Rebased / Session toggle
    • Moving dot with momentum-based color
    """

    REFRESH_INTERVAL_MS = 3000  # 3 seconds

    COLOR_UP = "#26A69A"     # green
    COLOR_DOWN = "#EF5350"   # red
    COLOR_FLAT = "#8A9BA8"   # grey

    def __init__(
        self,
        kite,
        instrument_token,
        symbol: str,
        parent=None
    ):
        super().__init__(parent)

        self.kite = kite
        self.instrument_token = instrument_token
        self.symbol = symbol

        self.cvd_df = None
        self.prev_day_close_cvd = 0.0
        self.rebased_mode = True

        self.axis = pg.AxisItem(orientation="bottom")

        self._setup_ui()
        self._load_historical()
        self._start_refresh_timer()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)

        self.title_label = QLabel(f"{self.symbol} (Rebased)")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #E0E0E0;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        header.addWidget(self.title_label)
        header.addStretch()

        self.toggle_btn = QPushButton("Rebased CVD")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #212635;
                border: 1px solid #3A4458;
                border-radius: 6px;
                padding: 4px 8px;
                color: #A9B1C3;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #2A3B5C;
                color: #FFFFFF;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_mode)
        header.addWidget(self.toggle_btn)

        root.addLayout(header)

        self.plot = pg.PlotWidget(axisItems={"bottom": self.axis})
        self.plot.setBackground("#161A25")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setMouseEnabled(x=False, y=True)
        self.plot.setMenuEnabled(False)

        zero_pen = pg.mkPen("#8A9BA8", style=Qt.DashLine, width=1)
        self.zero_line = pg.InfiniteLine(0, angle=0, pen=zero_pen)
        self.plot.addItem(self.zero_line)

        axis_pen = pg.mkPen("#8A9BA8")
        self.plot.getAxis("left").setPen(axis_pen)
        self.plot.getAxis("bottom").setPen(axis_pen)

        # Moving dot (color updated dynamically)
        self.end_dot = pg.ScatterPlotItem(
            size=6,
            brush=pg.mkBrush(self.COLOR_FLAT),
            pen=pg.mkPen(None)
        )
        self.plot.addItem(self.end_dot)

        root.addWidget(self.plot)

    # ------------------------------------------------------------------
    # Historical load
    # ------------------------------------------------------------------

    def _load_historical(self):
        if not self.kite or not getattr(self.kite, "access_token", None):
            return

        try:
            to_dt = datetime.now()
            from_dt = to_dt - timedelta(days=2)

            hist = self.kite.historical_data(
                self.instrument_token,
                from_dt,
                to_dt,
                interval="minute"
            )

            if not hist:
                return

            df = pd.DataFrame(hist)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

            cvd_df = CVDHistoricalBuilder.build_cvd_ohlc(df)

            cvd_df["session"] = cvd_df.index.date
            sessions = sorted(cvd_df["session"].unique())[-2:]
            cvd_df = cvd_df[cvd_df["session"].isin(sessions)]

            if len(sessions) == 2:
                prev_sess = sessions[0]
                self.prev_day_close_cvd = (
                    cvd_df[cvd_df["session"] == prev_sess]["close"].iloc[-1]
                )
            else:
                self.prev_day_close_cvd = 0.0

            self.cvd_df = cvd_df
            self._plot()

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Plotting + Momentum Dot
    # ------------------------------------------------------------------

    def _plot(self):
        if self.cvd_df is None or self.cvd_df.empty:
            return

        self.plot.clear()
        self.plot.addItem(self.zero_line)
        self.plot.addItem(self.end_dot)

        sessions = sorted(self.cvd_df["session"].unique())
        all_times = list(self.cvd_df.index)

        x_offset = 0
        last_two_y = []

        for i, sess in enumerate(sessions):
            df_sess = self.cvd_df[self.cvd_df["session"] == sess]
            y_raw = df_sess["close"].values

            if self.rebased_mode and i == 0 and len(sessions) == 2:
                y = y_raw - self.prev_day_close_cvd
            else:
                y = y_raw

            x = list(range(x_offset, x_offset + len(y)))

            pen = (
                pg.mkPen("#7A7A7A", width=1.2)
                if i == 0 and len(sessions) == 2
                else pg.mkPen("#26A69A", width=1.6)
            )

            self.plot.addItem(pg.PlotCurveItem(x, y, pen=pen))

            if i == len(sessions) - 1 and len(y) >= 2:
                last_two_y = y[-2:].tolist()
                last_x = x[-1]
                last_y = y[-1]

            x_offset += len(y)

        # --- Momentum logic ---
        if len(last_two_y) == 2:
            prev_y, curr_y = last_two_y

            if curr_y > prev_y:
                color = self.COLOR_UP
            elif curr_y < prev_y:
                color = self.COLOR_DOWN
            else:
                color = self.COLOR_FLAT

            self.end_dot.setBrush(pg.mkBrush(color))
            self.end_dot.setData([last_x], [last_y])
        else:
            self.end_dot.clear()

        def time_formatter(values, *_):
            out = []
            for v in values:
                idx = int(v)
                if 0 <= idx < len(all_times):
                    out.append(all_times[idx].strftime("%H:%M"))
                else:
                    out.append("")
            return out

        self.axis.tickStrings = time_formatter
        self.axis.setTickSpacing(major=60, minor=15)

        self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        self.plot.setXRange(0, x_offset, padding=0.02)

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    def _start_refresh_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._load_historical)
        self.timer.start(self.REFRESH_INTERVAL_MS)

    # ------------------------------------------------------------------
    # Toggle
    # ------------------------------------------------------------------

    def _toggle_mode(self):
        self.rebased_mode = self.toggle_btn.isChecked()

        if self.rebased_mode:
            self.toggle_btn.setText("Rebased CVD")
            self.title_label.setText(f"{self.symbol} (Rebased)")
        else:
            self.toggle_btn.setText("Session CVD")
            self.title_label.setText(self.symbol)

        self._plot()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if hasattr(self, "timer"):
            self.timer.stop()
        super().closeEvent(event)

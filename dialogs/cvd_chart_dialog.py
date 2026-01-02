import logging
from datetime import datetime, timedelta

import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from pyqtgraph import AxisItem

from kiteconnect import KiteConnect

from core.cvd.cvd_historical import CVDHistoricalBuilder

logger = logging.getLogger(__name__)


class CVDChartDialog(QDialog):
    """
    Historical CVD Chart with 1-minute auto-refresh

    - Previous day: grey, dashed
    - Current day: solid green
    - Auto-refreshes every 1 minute
    """

    REFRESH_INTERVAL_MS =3000  # 1 minute

    def __init__(
            self,
            kite: KiteConnect,
            instrument_token: int,
            symbol: str,
            cvd_engine=None,  # Not used anymore, kept for compatibility
            parent=None,
    ):
        super().__init__(parent)

        self.kite = kite
        self.instrument_token = instrument_token
        self.symbol = symbol

        self.setWindowTitle(f"CVD — {symbol}")
        self.setMinimumSize(900, 520)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self._setup_ui()
        self._load_and_plot()
        self._start_refresh_timer()

    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # Status bar at top
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #8A9BA8;
                font-size: 11px;
                padding: 4px 8px;
            }
        """)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # Chart
        self.axis = AxisItem(orientation="bottom")
        self.plot = pg.PlotWidget(axisItems={"bottom": self.axis})
        self.plot.setBackground("#161A25")
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=True)

        axis_pen = pg.mkPen("#8A9BA8")
        for a in ("left", "bottom"):
            ax = self.plot.getAxis(a)
            ax.setPen(axis_pen)
            ax.setTextPen(axis_pen)
            ax.setStyle(tickTextOffset=8)

        main_layout.addWidget(self.plot)

        # Zero line
        zero_pen = pg.mkPen("#6C7386", style=Qt.DashLine, width=1)
        self.plot.addItem(pg.InfiniteLine(0, angle=0, pen=zero_pen))

        # Curves
        self.prev_curve = pg.PlotCurveItem(
            pen=pg.mkPen("#7A7A7A", width=2, style=Qt.DashLine),
            antialias=True,
        )
        self.today_curve = pg.PlotCurveItem(
            pen=pg.mkPen("#26A69A", width=2.5),
            antialias=True,
        )

        self.plot.addItem(self.prev_curve)
        self.plot.addItem(self.today_curve)

    # ------------------------------------------------------------------

    def _load_and_plot(self):
        """Load historical data and plot CVD."""
        if not self.kite or not getattr(self.kite, "access_token", None):
            self.status_label.setText("⚠️ No API connection")
            return

        try:
            self.status_label.setText("Loading data...")

            to_date = datetime.now()
            from_date = to_date - timedelta(days=2)

            hist = self.kite.historical_data(
                self.instrument_token,
                from_date,
                to_date,
                interval="minute",
            )

            if not hist:
                self.status_label.setText("⚠️ No data available")
                return

            df = pd.DataFrame(hist)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

            # Build CVD
            cvd_df = CVDHistoricalBuilder.build_cvd_ohlc(df)
            cvd_df["session"] = cvd_df.index.date

            # Get last 2 sessions
            sessions = sorted(cvd_df["session"].unique())[-2:]
            plot_df = cvd_df[cvd_df["session"].isin(sessions)]

            # Plot
            self._plot_data(plot_df)

            # Update status
            last_time = plot_df.index[-1].strftime("%H:%M:%S")
            last_cvd = plot_df["close"].iloc[-1]
            self.status_label.setText(
                f"✓ Last update: {last_time} | CVD: {last_cvd:,.0f}"
            )

            logger.info(f"CVD chart updated for {self.symbol}")

        except Exception as e:
            logger.exception("Failed to load/plot CVD")
            self.status_label.setText(f"⚠️ Error: {str(e)[:50]}")

    # ------------------------------------------------------------------

    def _plot_data(self, cvd_df: pd.DataFrame):
        """Plot CVD data."""
        if cvd_df is None or cvd_df.empty:
            return

        x = 0
        all_times = []

        for i, session in enumerate(sorted(cvd_df["session"].unique())):
            df_sess = cvd_df[cvd_df["session"] == session]
            y = df_sess["close"].values
            xs = list(range(x, x + len(y)))

            all_times.extend(df_sess.index)

            # Previous day vs today
            if i == 0 and len(cvd_df["session"].unique()) == 2:
                self.prev_curve.setData(xs, y)
            else:
                self.today_curve.setData(xs, y)

            x += len(y)

        # Time axis formatter
        def time_formatter(values, *_):
            labels = []
            total = len(all_times)
            step = 15 if total <= 300 else 30 if total <= 600 else 60

            for v in values:
                idx = int(v)
                if 0 <= idx < total:
                    ts = all_times[idx]
                    labels.append(
                        ts.strftime("%H:%M") if ts.minute % step == 0 else ""
                    )
                else:
                    labels.append("")
            return labels

        self.axis.tickStrings = time_formatter

        # Auto-range
        self.plot.setXRange(0, x, padding=0.02)
        self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)

    # ------------------------------------------------------------------

    def _start_refresh_timer(self):
        """Start 1-minute auto-refresh."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_and_plot)
        self.refresh_timer.start(self.REFRESH_INTERVAL_MS)

        logger.info(f"CVD auto-refresh started (every 1s)")

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Cleanup on close."""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        logger.info(f"CVD chart closed for {self.symbol}")
        super().closeEvent(event)
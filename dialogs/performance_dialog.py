import logging
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal  # Import Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class PerformanceDialog(QDialog):
    """
    An advanced, professional dialog to display trading performance.
    """
    # FIX: Add a signal that the main window can connect to.
    refresh_requested = Signal()

    def __init__(self, mode: str = "live", parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.mode = mode.lower()
        if self.mode not in ["live", "paper"]:
            logger.warning(f"Invalid mode '{self.mode}' provided. Defaulting to 'live'.")
            self.mode = "live"

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(f"{self.mode.capitalize()} Performance Dashboard")
        self.setMinimumSize(800, 650)

        self._init_ui()
        self._connect_signals()
        self._apply_styles()

        self._plot_equity_curve(self._load_pnl_history())
        self.update_metrics({})

    def _get_history_filepath(self) -> Path:
        history_dir = Path(__file__).parent / "pnl_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        return history_dir / f"{self.mode}_pnl_history.json"

    def _init_ui(self):
        container = QWidget(self)
        container.setObjectName("mainContainer")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 10, 20, 20)
        container_layout.setSpacing(20)

        container_layout.addLayout(self._create_header())
        grid_layout = self._create_metrics_grid()
        container_layout.addLayout(grid_layout)

        self.chart_widget = self._create_chart_widget()
        container_layout.addWidget(self.chart_widget, 1)

    def _create_header(self) -> QHBoxLayout:
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"{self.mode.capitalize()} Performance")
        title.setObjectName("dialogTitle")

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("navButton")

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeButton")

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        header_layout.addWidget(self.close_btn)
        return header_layout

    def _connect_signals(self):
        """Connects UI element signals to corresponding slots."""
        self.close_btn.clicked.connect(self.close)
        # FIX: Make the refresh button emit our new signal.
        self.refresh_btn.clicked.connect(self.refresh_requested)

    # ... (The rest of the file remains the same, but the sample data method is now gone)
    # FIX: The _refresh_with_sample_data method has been completely removed.

    def _create_chart_widget(self) -> pg.PlotWidget:
        date_axis = pg.DateAxisItem(orientation='bottom')
        plot_widget = pg.PlotWidget(axisItems={'bottom': date_axis})

        plot_widget.setBackground("transparent")
        plot_widget.showGrid(x=True, y=True, alpha=0.2)
        plot_widget.getPlotItem().hideButtons()

        axis_pen = pg.mkPen(color="#B0BEC5", width=1)
        plot_widget.getAxis('left').setPen(axis_pen)
        plot_widget.getAxis('bottom').setPen(axis_pen)
        plot_widget.getAxis('left').setTextPen(axis_pen.color())
        plot_widget.getAxis('bottom').setTextPen(axis_pen.color())

        plot_widget.setLabel('left', "Total P&L (₹)", color="#B0BEC5")
        plot_widget.setLabel('bottom', "Date", color="#B0BEC5")

        return plot_widget

    def _create_metrics_grid(self) -> QGridLayout:
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        self.labels = {}

        self.labels['total_pnl'] = self._create_metric_widget("All-Time P&L", grid_layout, 0, 0)
        self.labels['win_rate'] = self._create_metric_widget("Win Rate", grid_layout, 0, 1)
        self.labels['avg_profit'] = self._create_metric_widget("Average Win", grid_layout, 0, 2)
        self.labels['avg_loss'] = self._create_metric_widget("Average Loss", grid_layout, 0, 3)
        self.labels['risk_reward_ratio'] = self._create_metric_widget("Risk/Reward Ratio", grid_layout, 1, 0)
        self.labels['total_trades'] = self._create_metric_widget("Total Trades", grid_layout, 1, 1)
        self.labels['winning_trades'] = self._create_metric_widget("Winning Trades", grid_layout, 1, 2)
        self.labels['losing_trades'] = self._create_metric_widget("Losing Trades", grid_layout, 1, 3)
        return grid_layout

    @staticmethod
    def _create_metric_widget(title_text, layout, row, col) -> QLabel:
        metric_box = QWidget()
        metric_box.setObjectName("metricFrame")
        metric_layout = QVBoxLayout(metric_box)
        metric_layout.setContentsMargins(15, 12, 15, 12)
        metric_layout.setSpacing(5)

        value_label = QLabel("N/A")
        value_label.setObjectName("metricValueLabel")
        title_label = QLabel(title_text)
        title_label.setObjectName("metricTitleLabel")

        metric_layout.addWidget(title_label, 0, Qt.AlignTop)
        metric_layout.addWidget(value_label, 1, Qt.AlignBottom)

        layout.addWidget(metric_box, row, col)
        return value_label

    def _load_pnl_history(self) -> dict:
        filepath = self._get_history_filepath()
        if not filepath.exists():
            return {}
        try:
            with open(filepath, "r") as f:
                content = f.read()
                if not content: return {}
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load P&L history from {filepath}: {e}")
            return {}

    def _update_pnl_history(self, current_pnl: float) -> dict:
        history = self._load_pnl_history()
        today_str = datetime.now().strftime('%Y-%m-%d')
        history[today_str] = current_pnl
        filepath = self._get_history_filepath()
        try:
            with open(filepath, "w") as f:
                json.dump(history, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save P&L history to {filepath}: {e}")
        return history

    def _plot_equity_curve(self, pnl_history: dict):
        self.chart_widget.clear()
        if not pnl_history:
            return
        try:
            sorted_history = sorted(pnl_history.items(), key=lambda x: datetime.strptime(x[0], '%Y-%m-%d'))
            dates = [datetime.strptime(item[0], '%Y-%m-%d').timestamp() for item in sorted_history]
            pnl_values = [item[1] for item in sorted_history]
            self.chart_widget.plot(x=dates, y=pnl_values, pen=pg.mkPen(color="#1DE9B6", width=2))
        except (ValueError, TypeError) as e:
            logger.error(f"Error plotting equity curve with data {pnl_history}: {e}")

    def update_metrics(self, metrics: dict):
        profit_color, loss_color = "#1DE9B6", "#F85149"
        pnl_history = self._load_pnl_history()
        if 'total_pnl' in metrics:
            total_pnl = metrics.get('total_pnl', 0.0)
            pnl_history = self._update_pnl_history(total_pnl)
        else:
            if pnl_history:
                last_date = max(pnl_history.keys())
                total_pnl = pnl_history.get(last_date, 0.0)
            else:
                total_pnl = 0.0
        self._plot_equity_curve(pnl_history)
        pnl_label = self.labels.get('total_pnl')
        if pnl_label:
            pnl_label.setText(f"₹{int(total_pnl):,}")
            pnl_label.setStyleSheet(f"color: {profit_color if total_pnl >= 0 else loss_color};")
        win_rate = metrics.get('win_rate', 0.0)
        win_rate_label = self.labels.get('win_rate')
        if win_rate_label:
            win_rate_label.setText(f"{win_rate:.1f}%")
            win_rate_label.setStyleSheet(f"color: {profit_color if win_rate >= 50 else loss_color};")
        self.labels.get('winning_trades', QLabel()).setText(str(metrics.get('winning_trades', 'N/A')))
        self.labels.get('losing_trades', QLabel()).setText(str(metrics.get('losing_trades', 'N/A')))
        self.labels.get('total_trades', QLabel()).setText(str(metrics.get('total_trades', 'N/A')))
        avg_profit = metrics.get('avg_profit', 0.0)
        self.labels.get('avg_profit', QLabel()).setText(f"₹{int(avg_profit):,}")
        avg_loss = metrics.get('avg_loss', 0.0)
        self.labels.get('avg_loss', QLabel()).setText(f"₹{int(avg_loss):,}")
        rr_label = self.labels.get('risk_reward_ratio')
        if rr_label and avg_profit is not None and avg_loss is not None and avg_loss != 0:
            ratio = abs(avg_profit / avg_loss)
            if ratio < 1: rating, color = "(Bad)", loss_color
            elif 1 <= ratio < 2: rating, color = "(Not Bad)", "#F39C12"
            else: rating, color = "(Good)", profit_color
            rr_label.setText(f"{ratio:.2f} : 1  <span style='color:{color};'>{rating}</span>")
        elif rr_label:
            rr_label.setText("N/A")

    def _apply_styles(self):
        self.setStyleSheet("""
            #mainContainer { background-color: #161A25; border: 1px solid #3A4458; border-radius: 12px; font-family: "Segoe UI", sans-serif; }
            #dialogTitle { color: #FFFFFF; font-size: 18px; font-weight: 600; }
            #closeButton, #navButton { background-color: transparent; border: 1px solid #3A4458; color: #A9B1C3; font-size: 12px; font-weight: bold; border-radius: 4px; padding: 6px 12px; }
            #closeButton:hover { background-color: #F85149; color: white; border-color: #F85149; }
            #navButton:hover { background-color: #29C7C9; color: #161A25; border-color: #29C7C9; }
            #metricFrame { background: #212635; border: 1px solid #3A4458; border-radius: 8px; }
            #metricFrame:hover { border-color: rgba(29, 233, 182, 0.6); }
            #metricTitleLabel { color: #B0BEC5; font-size: 10px; font-weight: 700; text-transform: uppercase; background: transparent; }
            #metricValueLabel { color: #FFFFFF; font-size: 20px; font-weight: 600; font-family: 'Segoe UI', 'Roboto Mono', monospace; background: transparent; }
        """)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        event.accept()
import logging
from PySide6.QtWidgets import QDialog, QGridLayout
from PySide6.QtCore import Qt

from widgets.cvd_chart_widget import CVDChartWidget

logger = logging.getLogger(__name__)


class CVDMarketMonitorDialog(QDialog):
    """
    Market Monitor style dialog for CVD charts (2x2 grid).

    Each tile uses historical candle pulls (minute data)
    with periodic refresh — no live tick dependency.
    """

    def __init__(
        self,
        kite,
        symbol_to_token: dict,
        parent=None
    ):
        super().__init__(parent)

        self.kite = kite
        self.symbol_to_token = symbol_to_token or {}

        self.setWindowTitle("CVD Market Monitor")
        self.setMinimumSize(1200, 700)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self._setup_ui()

    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        if not self.symbol_to_token:
            logger.warning("CVD Market Monitor opened with empty symbol list")
            return

        symbols = list(self.symbol_to_token.keys())

        for idx, symbol in enumerate(symbols):
            instrument_token = self.symbol_to_token.get(symbol)

            if not instrument_token:
                logger.warning(f"Missing instrument token for symbol: {symbol}")
                continue

            try:
                widget = CVDChartWidget(
                    kite=self.kite,
                    instrument_token=instrument_token,
                    symbol=f"{symbol} FUT",
                    parent=self
                )

                row = idx // 2
                col = idx % 2
                layout.addWidget(widget, row, col)

            except Exception:
                logger.exception(f"Failed to create CVD widget for {symbol}")

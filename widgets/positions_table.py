import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QStyledItemDelegate, QStyle, QApplication, QStyleOptionButton)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette, QPainter, QFont

from utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class PositionsTable(QWidget):
    """
    A compound widget containing a compact, data-dense positions table and a summary footer.
    """
    exit_requested = Signal(dict)
    refresh_requested = Signal()

    SYMBOL_COL = 0
    QUANTITY_COL = 1
    AVG_PRICE_COL = 2
    LTP_COL = 3
    PNL_COL = 4

    class PnlExitDelegate(QStyledItemDelegate):
        """Custom delegate to render the P&L column with a hover-to-exit button."""

        def paint(self, painter, option, index):
            if index.column() != PositionsTable.PNL_COL:
                super().paint(painter, option, index)
                return

            table = self.parent()
            is_hovered = (hasattr(table, 'hovered_row') and table.hovered_row == index.row())

            if is_hovered:
                self.draw_exit_button(painter, option)
            else:
                self.draw_pnl_text(painter, option, index)

        def draw_exit_button(self, painter, option):
            painter.save()

            rect = option.rect

            # Enable antialiasing
            painter.setRenderHint(QPainter.Antialiasing)

            # Red background
            painter.setBrush(QColor("#F85149"))
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)

            # Draw white bold text
            painter.setPen(QColor("#FFFFFF"))
            font = QFont()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, "Exit")

            # Draw bottom separator line
            pen = painter.pen()
            pen.setColor(QColor("#2A3140"))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

            painter.restore()
        def draw_pnl_text(self, painter, option, index):
            painter.save()

            # Draw background (optional, depending on selection/highlight)
            painter.fillRect(option.rect, QColor("#161A25"))

            # Draw bottom border line manually
            border_color = QColor("#2A3140")
            pen = painter.pen()
            pen.setColor(border_color)
            pen.setWidth(1)
            painter.setPen(pen)
            bottom = option.rect.bottom()
            left = option.rect.left()
            right = option.rect.right()
            painter.drawLine(left, bottom, right, bottom)

            # Draw the P&L text
            pnl_value = index.data(Qt.UserRole) or 0.0
            text_color = QColor("#1DE9B6") if pnl_value >= 0 else QColor("#F85149")
            painter.setPen(text_color)

            display_text = f"{pnl_value:,.0f}"
            painter.drawText(option.rect, Qt.AlignCenter, display_text)

            painter.restore()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.table_name = "positions_table"
        self.positions = {}

        self._init_ui()
        self._apply_styles()
        self._connect_signals()

        self.table.hovered_row = -1

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.headers = ["Symbol", "Qty", "Avg", "LTP", "P&L"]
        self.table.setColumnCount(len(self.table.headers))
        self.table.setHorizontalHeaderLabels(self.table.headers)
        self.table.setItemDelegate(self.PnlExitDelegate(self.table))
        self.table.setMouseTracking(True)
        main_layout.addWidget(self.table, 1)

        footer_widget = QWidget()
        footer_widget.setObjectName("footer")
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(10, 5, 10, 5)

        self.total_pnl_label = QLabel("Total P&L: ₹ 0")
        self.total_pnl_label.setObjectName("footerLabel")

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("footerButton")

        footer_layout.addWidget(self.total_pnl_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.refresh_button)
        main_layout.addWidget(footer_widget)

    def _apply_styles(self):
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.SYMBOL_COL, QHeaderView.ResizeMode.Stretch)

        # --- FIX: PNL_COL is now handled separately to allow for custom width ---
        for i in [self.QUANTITY_COL, self.AVG_PRICE_COL, self.LTP_COL]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Set P&L column to be interactive so we can manually set its width
        header.setSectionResizeMode(self.PNL_COL, QHeaderView.ResizeMode.Interactive)

        stylesheet = """
            QTableWidget {
                background-color: #161A25;
                color: #E0E0E0;
                border: none;
                font-size: 13px;
                gridline-color: transparent;
            }
            QHeaderView::section {
                background-color: #2A3140;
                color: #A9B1C3;
                padding: 4px;
                border: none;
                font-weight: 600;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #2A3140;
            }
            QTableWidget::item:selected {
                background-color: #161A25;
                color: #E0E0E0;
            }
            #footer {
                background-color: #212635;
                border-top: 1px solid #3A4458;
            }
            #footerLabel {
                color: #E0E0E0;
                font-size: 13px;
                font-weight: 600;
            }
            #footerButton {
                background-color: transparent;
                color: #A9B1C3;
                border: 1px solid #3A4458;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            #footerButton:hover {
                background-color: #29C7C9;
                color: #161A25;
            }
        """
        self.setStyleSheet(stylesheet)

    def _connect_signals(self):
        self.table.cellPressed.connect(self._on_cell_pressed)
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.table.mouseMoveEvent = self.mouseMoveEvent
        self.table.leaveEvent = self.leaveEvent

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        row = self.table.rowAt(pos.y())
        col = self.table.columnAt(pos.x())

        new_hover_row = row if col == self.PNL_COL else -1

        if new_hover_row != self.table.hovered_row:
            self.table.hovered_row = new_hover_row
            self.table.viewport().update()

        QTableWidget.mouseMoveEvent(self.table, event)

    def leaveEvent(self, event):
        if self.table.hovered_row != -1:
            self.table.hovered_row = -1
            self.table.viewport().update()
        QTableWidget.leaveEvent(self.table, event)

    def _on_cell_pressed(self, row, column):
        if column == self.PNL_COL:
            symbol_item = self.table.item(row, self.SYMBOL_COL)
            if symbol_item:
                symbol = symbol_item.text()
                if symbol in self.positions:
                    logger.info(f"Exit requested for '{symbol}' from P&L column press.")
                    self.exit_requested.emit(self.positions[symbol])

    def update_positions(self, positions_data):
        self.table.setRowCount(0)
        self.positions.clear()
        for pos in positions_data:
            self.add_position(pos)
        self._update_footer()

        # --- FIX: Resize P&L column after data is populated and add padding ---
        self.table.resizeColumnToContents(self.PNL_COL)
        current_width = self.table.columnWidth(self.PNL_COL)
        self.table.setColumnWidth(self.PNL_COL, current_width + 25)

    def add_position(self, pos_data: dict):
        symbol = pos_data['tradingsymbol']
        self.positions[symbol] = pos_data

        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        self._set_item(row_position, self.SYMBOL_COL, symbol, is_text=True)
        self._set_item(row_position, self.QUANTITY_COL, pos_data.get('quantity', 0))
        self._set_item(row_position, self.AVG_PRICE_COL, pos_data.get('average_price', 0.0), is_price=True)
        self._set_item(row_position, self.LTP_COL, pos_data.get('last_price', 0.0), is_price=True)
        self._set_pnl_item(row_position, self.PNL_COL, pos_data.get('pnl', 0.0))

    def _update_footer(self):
        total_pnl = sum(pos.get('pnl', 0.0) for pos in self.positions.values())

        pnl_text = f"Total P&L: ₹ {total_pnl:,.0f}"
        self.total_pnl_label.setText(pnl_text)

        pnl_color = "#1DE9B6" if total_pnl >= 0 else "#F85149"
        self.total_pnl_label.setStyleSheet(f"color: {pnl_color}; font-weight: 600;")

    def _set_item(self, row, col, data, is_text=False, is_price=False):
        item = QTableWidgetItem()
        if is_text:
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setText(str(data))
        else:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if is_price:
                item.setText(f"{data:,.2f}")
            else:
                item.setText(f"{int(data):,}")

        self.table.setItem(row, col, item)

    def _set_pnl_item(self, row, col, pnl_value):
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, pnl_value)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def save_column_widths(self):
        pass

    def load_column_widths(self):
        pass
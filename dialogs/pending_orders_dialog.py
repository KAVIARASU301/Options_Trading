import logging
from typing import List, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)


class PendingOrdersDialog(QDialog):
    """
    A premium dialog to display orders that are pending, featuring the
    consistent rich and modern dark theme of the application.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self._setup_window()
        self._setup_ui()
        self._apply_styles()

    def _setup_window(self):
        """Configure window properties for the custom frameless design."""
        self.setWindowTitle("Pending Orders")
        self.setMinimumSize(750, 400)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _setup_ui(self):
        """Initialize the main UI components with the new premium layout."""
        container = QWidget(self)
        container.setObjectName("mainContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 10, 20, 20)
        container_layout.setSpacing(15)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        container_layout.addLayout(self._create_header())

        # Create both table and the label for the empty state
        self.orders_table = self._create_table()
        self.no_orders_label = QLabel("No Pending Orders")
        self.no_orders_label.setObjectName("noOrdersLabel")

        container_layout.addWidget(self.orders_table, 1)
        container_layout.addWidget(self.no_orders_label, 1)

        # Initially, show the table and hide the label
        self.no_orders_label.hide()

    def _create_header(self):
        """Creates a custom title bar with a title and close button."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Pending Orders")
        title.setObjectName("dialogTitle")

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self.close)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.close_btn)
        return header_layout

    @staticmethod
    def _create_table():
        """Creates and configures the main table for pending orders."""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Symbol", "Type", "Qty", "Price", "Status"
        ])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)

        # Set fixed, realistic widths for all columns
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 220)  # Symbol
        table.setColumnWidth(1, 80)  # Type
        table.setColumnWidth(2, 80)  # Qty
        table.setColumnWidth(3, 100)  # Price
        table.setColumnWidth(4, 100)  # Status
        return table

    def update_orders(self, orders: List[Dict]):
        """Populates the table or shows a message if no orders are pending."""
        if orders:
            self.orders_table.setVisible(True)
            self.no_orders_label.setVisible(False)
            self.orders_table.setRowCount(len(orders))
            for row, order in enumerate(orders):
                self._populate_row(row, order)
        else:
            # Show the "No Pending Orders" message
            self.orders_table.setVisible(False)
            self.no_orders_label.setVisible(True)
            self.orders_table.setRowCount(0)  # Clear table content

    def _populate_row(self, row, order_data):
        """Populates a single row with data from a pending order."""
        self.orders_table.setItem(row, 0, QTableWidgetItem(order_data.get("tradingsymbol", "")))

        type_item = QTableWidgetItem(order_data.get("transaction_type", ""))
        type_color = "#29C7C9" if "BUY" in type_item.text() else "#F85149"
        type_item.setForeground(QColor(type_color))
        self.orders_table.setItem(row, 1, type_item)

        self.orders_table.setItem(row, 2, QTableWidgetItem(str(order_data.get("quantity", 0))))
        self.orders_table.setItem(row, 3, QTableWidgetItem(f"₹{order_data.get('price', 0.0):.2f}"))

        status_item = QTableWidgetItem(order_data.get("status", "").upper())
        status_item.setForeground(QColor("#F39C12"))
        self.orders_table.setItem(row, 4, status_item)

        for col in range(5):
            item = self.orders_table.item(row, col)
            if item:
                if col > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

    def _apply_styles(self):
        """Applies the application's consistent rich, dark theme."""
        self.setStyleSheet("""
            #mainContainer {
                background-color: #161A25;
                border: 1px solid #3A4458;
                border-radius: 12px;
                font-family: "Segoe UI", sans-serif;
            }
            #dialogTitle {
                color: #E0E0E0;
                font-size: 18px;
                font-weight: 600;
            }
            #noOrdersLabel {
                color: #A9B1C3;
                font-size: 16px;
                font-weight: 500;
                qproperty-alignment: 'AlignCenter';
            }
            #closeButton {
                background-color: transparent; border: none; color: #A9B1C3;
                font-size: 16px; font-weight: bold; border-radius: 4px;
            }
            #closeButton:hover { background-color: #F85149; color: white; }

            QTableWidget {
                background-color: #1A1F2C;
                color: #E0E0E0;
                border: 1px solid #2A3140;
                border-radius: 8px;
                gridline-color: #2A3140;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 12px 10px;
                border: none;
            }
            QTableWidget::item:hover {
                background-color: #212635;
            }
            QTableWidget::item:alternate {
                background-color: #161A25;
            }
            QHeaderView::section {
                background-color: #212635;
                color: #A9B1C3;
                padding: 12px 8px;
                border: none;
                border-bottom: 2px solid #3A4458;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
            }
            QScrollBar:vertical {
                border: none;
                background: #161A25;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #3A4458;
                border-radius: 5px;
                min-height: 25px;
            }
            QScrollBar::handle:vertical:hover { background: #4A5568; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


from PyQt5.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QPushButton, QFileDialog, 
                             QTableView, QVBoxLayout, QWidget, QLineEdit, QMessageBox, QRadioButton)
from PyQt5.QtCore import QAbstractTableModel, Qt, QTimer, QThread, pyqtSignal
from sqlalch_database_handling import SQLDataBase
from voice_ai import VoiceSearch
from PyQt5.QtGui import QColor
from numpy import int64
import pandas as pd
import datetime
import sys

'''
In this application if we click on the "Load CSV" button and afterwards we choosed the 'healthcare_dataset.csv'
the program load ~55.000 lines of data. Then the code get rid of the duplicated datas and normalize the low or uppercase letters.
The cleaned DataFrame is appear in the TableView section. 'Name' column background is green.
And we can modify each records with the correct data type.

We can use the "Search Field" and the "Voice Search" function to search for a specific name. 
And using the "Send all datas to dataframe" button will send all datas from the DataFrame to database file. After sent the datas
we see the content of the database by query the whole database.

Voice search and send datas to database with query are work on QThread.

I obtained the CSV file from the webpage of Kaggle.

But if you try to load another CSV file the application will implod.

'''


class DatabaseThread(QThread):
    '''
    pyqtSignal is an event handling. This work with .emit().
    
    '''
    
    finished = pyqtSignal(str)  # Signal to indicate that the thread has finished. 

    def __init__(self, data, db_handle):
        super().__init__()
        self.data = data
        self.db_handle = db_handle

    def run(self):
        try:
            self.db_handle.insert_into_db(self.data.copy(), pd)
            self.finished.emit("Data sent successfully!")  # Emit success message
            
            self.db_handle.query_from_db()
        except Exception as e:
            self.finished.emit(f"Something went wrong: {str(e)}")  # Emit error message


class VoiceSearchThread(QThread):
    finished = pyqtSignal(str)  # Signal to indicate that the voice search is finished

    def __init__(self, voice_search_instance):
        super().__init__()
        self.voice_search_instance = voice_search_instance

    def run(self):
        try:
            name = self.voice_search_instance.voice_command()
            self.finished.emit(name)  # Emit the recognized name
        except Exception as e:
            self.finished.emit("")  # Emit empty string on failure


class PandasModel(QAbstractTableModel):
    '''
    Convert the pandas DataFrame into a table view modell.
    
    '''
    def __init__(self, data, original_data, parent=None):
        super().__init__()
        self._data = data
        self.original_data = original_data  # Store the original data
        self.parent = parent

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        column_name = self._data.columns[index.column()]
        
        if role == Qt.DisplayRole:
            return str(self._data.iat[index.row(), index.column()])
        
        if role == Qt.BackgroundRole:
            if column_name == "Name":
                return QColor("#ccffcc") 

        return None

    def is_float(self, value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    def is_integer(self, value):
        try:
            int(value)
            return True
        except ValueError:
            return False

    def setData(self, index, value, role=Qt.EditRole): # Type check and control to modify the recod
        
        if index.isValid() and role == Qt.EditRole:
            column_name = self._data.columns[index.column()]
            original_value = self._data.iat[index.row(), index.column()]
            original_type = type(original_value)

            try:
                
                if original_type in (int, int64):  
                    if self.is_integer(value):
                        value = int(value)
                    else:
                        raise ValueError("Not Int64")
                elif isinstance(original_value, float):
                    value = float(value)
                elif isinstance(original_value, pd.Timestamp) or isinstance(original_value, datetime.date):  
                    new_date = pd.to_datetime(value, errors='coerce')
                    if pd.isnull(new_date):
                        raise ValueError("Wrong date format")
                    value = new_date.date()
                elif isinstance(original_value, str):
                    if self.is_integer(value) or self.is_float(value):
                        raise ValueError("Not string type")
                    value = str(value)
                else:
                    raise ValueError("Wrong type")

            except ValueError:
                msg_box = QMessageBox(self.parent)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("Type error")
                msg_box.setText(f"In the '{column_name}' of column the type {original_type.__name__} of value needed.")
                msg_box.exec_()
                return False  

            # Refresh the original DataFrame by index
            original_index = self._data.index[index.row()]  # Get the index of the original data
            original_row_index = self.original_data.index.get_loc(original_index)  # Get the location in original data
            self.original_data.iat[original_row_index, index.column()] = value  # Update the original data
            self._data.iat[index.row(), index.column()] = value
            
            modified_row = self.original_data.iloc[original_row_index]
            print(f"Modified original data: {modified_row}")
            self.dataChanged.emit(index, index)
            return True
        
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._data.columns[section]
            if orientation == Qt.Vertical:
                return str(self._data.index[section])
        return None

    def flags(self, index):
        if index.isValid():
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.NoItemFlags


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_handle_class = SQLDataBase()
        self.voice_search_class = VoiceSearch()
        self.db_thread = None
        self.model = None
        self.search_enabled = True
        
        self.setWindowTitle("Bányász Tamás")
        self.setFixedSize(1024, 768)
   
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)
        
        self.original_data = None
        self.search_delay = 300  
        self.search_timer = QTimer(self)  
        self.search_timer.setSingleShot(True)  
        self.search_timer.timeout.connect(self.execute_filter)
        
        self.button_layout = QHBoxLayout()
        self.button_layout.setAlignment(Qt.AlignLeft)
        
        self.load_button = QPushButton("Load CSV file", self)
        self.load_button.setFixedSize(100, 30)  
        self.load_button.clicked.connect(self.load_from_csv)
        self.button_layout.addWidget(self.load_button)
        
        self.send_to_db_button = QPushButton("All send to Database", self)
        self.send_to_db_button.setFixedSize(150, 30)  
        self.send_to_db_button.setEnabled(False) 
        self.send_to_db_button.clicked.connect(self.send_to_database)
        self.button_layout.addWidget(self.send_to_db_button)
        
        self.layout.addLayout(self.button_layout)
        
        self.search_radio = QRadioButton("Enable Search")
        self.search_radio.setChecked(True)  
        self.search_radio.toggled.connect(self.toggle_search)
        self.layout.addWidget(self.search_radio)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search name...")
        self.search_box.setFixedSize(200, 30)  
        self.search_box.setStyleSheet("""QLineEdit {
            border: 2px solid gray;
            border-radius: 5px;
            padding: 5px;
        }""")
        
        self.voice_search_button = QPushButton("Voice search", self)
        self.voice_search_button.setFixedSize(100, 30)
        self.voice_search_button.clicked.connect(self.voice_search)
        self.layout.addWidget(self.voice_search_button)
        
        self.search_box.textChanged.connect(self.schedule_filter)
        self.layout.addWidget(self.search_box)
        
        self.voice_search_button.setStyleSheet(""" 
            QPushButton {
                border: 2px solid red;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }""")
        
        self.table_view = QTableView()  
        self.layout.addWidget(self.table_view)

        self.table_view.setSelectionMode(QTableView.SingleSelection) 
        self.table_view.setSelectionBehavior(QTableView.SelectItems)

        self.table_view.setModel(None)  # Initialize model to avoid NoneType error
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

    def toggle_search(self):
        self.search_enabled = self.search_radio.isChecked()  
        self.search_box.setVisible(self.search_enabled)

        if not self.search_enabled:
            self.search_box.clear()  
            self.execute_filter()  
    
    def load_from_csv(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)", options=options)

        if file_name:
            df = pd.read_csv(file_name)
            df.columns = df.columns.str.strip()  # Remove any leading or trailing spaces

            # Check if 'Name' column exists
            if 'Name' not in df.columns:
                print("The 'Name' column is missing from the DataFrame.")
                return  # Don't continue if 'Name' column is missing
            
            initial_length = len(df)
            df = df.drop_duplicates()
            df = df.loc[df['Name'].duplicated(keep='first') == False]
            df['Name'] = df['Name'].str.title()
            final_length = len(df)
            df = df.reset_index(drop=True)
            df.index = pd.Index(range(1, len(df) + 1))

            
            print(f"Initial length of DataFrame: {initial_length}")
            print(f"Final length of DataFrame: {final_length}")
            
            # convert the dates to the correct date type
            date_columns = [col for col in df.columns.tolist() if "date" in col.lower()]
            for col in date_columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

            self.original_data = df.copy()  # Store a copy of the original data

            self.model = PandasModel(df, self.original_data, self)
            self.table_view.setModel(self.model)  
            self.send_to_db_button.setEnabled(True)  
            
            self.execute_filter()  

    def execute_filter(self):
        if self.original_data is not None:
            filter_text = self.search_box.text().strip().lower()
            filtered_data = self.original_data[self.original_data['Name'].str.contains(filter_text, case=False, na=False)]
            self.model._data = filtered_data
            self.model.layoutChanged.emit()  

    def schedule_filter(self):
        self.search_timer.start(self.search_delay)

    def send_to_database(self):
        if self.original_data is not None:
            self.db_thread = DatabaseThread(self.original_data, self.db_handle_class)
            self.db_thread.finished.connect(self.on_db_finished)
            self.db_thread.start()

    def on_db_finished(self, message):
        msg_box = QMessageBox(self)
        msg_box.setText(message)
        msg_box.exec_()

    def voice_search(self):
        if self.original_data is None:
            QMessageBox.warning(self, "Warning", "Please load a CSV file first!")
            return
        
        self.voice_search_button.setStyleSheet(""" 
            QPushButton {
                border: 4px solid green;
                border-radius: 5px;
                padding: 5px;
                background-color: red;
            }
        """)
        self.voice_search_button.setEnabled(False)
        
        self.voice_search_thread = VoiceSearchThread(self.voice_search_class)
        self.voice_search_thread.finished.connect(self.on_voice_search_finished)
        self.voice_search_thread.start()
           

    def on_voice_search_finished(self, name):
        
        self.voice_search_button.setEnabled(True)
        
        if name:
            self.search_box.setText(name)
            self.voice_search_button.setStyleSheet("""
                QPushButton {
                    border: 2px solid red;
                    border-radius: 5px;
                    padding: 5px;
                    background-color: white;
                }""") 
            
        else:
            msg_box = QMessageBox(self)
            msg_box.setText("Voice command failed to recognize a name.")
            msg_box.exec_()
            self.voice_search_button.setStyleSheet("""
                QPushButton {
                    border: 2px solid red;
                    border-radius: 5px;
                    padding: 5px;
                    background-color: white;
                }""") 

    def on_selection_changed(self, selected, deselected):
        if self.table_view.selectionModel().hasSelection():
            selected_index = self.table_view.selectionModel().selectedIndexes()[0]
            selected_name = self.model.data(selected_index)
            self.search_box.setText(selected_name)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())












'''
Contribution partner was:
https://www.youtube.com/watch?v=DI1_qG8T9Uo

'''

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Date
from sqlalchemy import select, func

class SQLDataBase:
    def __init__(self):
        self.engine = create_engine('sqlite:///healthcare.db')
        self.connection = self.engine.connect()
        self.metadata = MetaData()
    

        # Table to SQLAlchemy 
        self.people_table = Table(
            'people', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('name', String),
            Column('age', Integer),
            Column('gender', String),
            Column('bloodtype', String),
            Column('medicalcondition', String),
            Column('dateofadmission', Date),
            Column('doctor', String),
            Column('hospital', String),
            Column('insuranceprovider', String),
            Column('billingamount', Integer),
            Column('roomnumber', Integer),
            Column('admissiontype', String),
            Column('dischargedate', Date),
            Column('medication', String),
            Column('testresults', String)
        )

        self.metadata.create_all(self.engine)

    def dataframe_to_dict(self, df, columns, pd):
        """
        Columns of the DataFrame convert to a structured form
        
        Parameters:
        - df: pandas DataFrame
        - columns: df column names
        - dyteps: columns with their data types by list
        
        Returns:
        - List of datas, it contents dictionarys
        """
        
        data = df[columns].apply(
        lambda col: col.astype(int) if pd.api.types.is_integer_dtype(col) else col
            ).to_dict(orient='records') 
    
        return data

    def insert_into_db(self, df, pd):

        # Prepar and transform data beore insert 
        df.columns = [col.lower().replace(' ', '') for col in df.columns]

        # Prepar the datas before insert they into database
        data = self.dataframe_to_dict(df, df.columns.to_list(), pd)


        try:
        # Insert data into the database
            with self.engine.begin() as connection:
                connection.execute(self.people_table.insert(), data)
            print("Insert successful")
        except Exception as e:
            print(f"Error during insertion: {e}")

    def query_from_db(self):
        with self.engine.connect() as connection:
            select_all_row_from_people_table = connection.execute(select(self.people_table)).mappings() 

            for person in select_all_row_from_people_table:
                print(f"Id: {person['id']}, Name: {person['name']}, Age: {person['age']}, Gender: {person['gender']}, "
                    f"Blood Type: {person['bloodtype']}, Medical Condition: {person['medicalcondition']}, "
                    f"Date of Admission: {person['dateofadmission']}, Doctor: {person['doctor']}, "
                    f"Hospital: {person['hospital']}, Insurance Provider: {person['insuranceprovider']}, "
                    f"Billing Amount: {person['billingamount']}, Room Number: {person['roomnumber']}, "
                    f"Admission Type: {person['admissiontype']}, Discharge Date: {person['dischargedate']}, "
                    f"Medication: {person['medication']}, Test Results: {person['testresults']} ...")

            select_length_of_the_db = select(func.count()).select_from(self.people_table)
            length_of_the_db = connection.execute(select_length_of_the_db)

            row_count = length_of_the_db.scalar()  
            print(f"Length of Table people: {row_count}")



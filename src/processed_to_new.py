from utils import get_db_connection
connection = get_db_connection()
cursor = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([row[0] for row in cursor.fetchall()])

connection.execute("UPDATE videos SET status = 'new'")
connection.commit()
connection.close()
print("Done.")


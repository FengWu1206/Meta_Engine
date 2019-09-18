import psycopg2
db_host = "XXX"
db_port = 5432
db_name = "XXX"
db_user = "XXX"
db_password = "XXX"

class postSql:
    def __init__(self, host_name, port, user, password, db_name):
        self.host_name = host_name
        self.port = port
        self.user = user
        self.password = password
        self.db_name = db_name
        self.client = psycopg2.connect(host=self.host_name, port=self.port, user=self.user, password=self.password, database=self.db_name)
    def query(self):
        cursor = self.client.cursor()
        cursor.execute("select * from scantist_library_version_checksum where (id = '4572');")
        records = cursor.fetchall()
        for record in records:
            print(record)
    def commit(self):
        self.client.commit()
    def close(self):
        self.client.close()

if __name__ == '__main__':
    try:
        post_sql = postSql(db_host, db_port, db_user, db_password, db_name)
        post_sql.query()
        post_sql.commit()
        post_sql.close()
    except Exception as e:
        print("error in query db: %s"%e)

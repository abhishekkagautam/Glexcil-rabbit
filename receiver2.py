

try :
    import pika
    import ast
    import pandas as pd
    import csv
    import datetime
    import time
    import mysql.connector
except Exception as e:
    print(e)

try:
    connection = mysql.connector.connect(host='localhost',
                                         database='Rabbit',
                                         user='root',
                                         password='admin')
    if connection.is_connected():
        db_Info = connection.get_server_info()
        print("Connected to MySQL Server version ", db_Info)
        cursor = connection.cursor()
        cursor.execute("select database();")
        record = cursor.fetchone()
        print("You're connected to database: ", record)
except Exception as e :
    print(e)


class MetaClass(type):
    _instance ={}
    def __call__(cls, *args, **kwargs) :
        if cls not in cls._instance:
            cls._instance[cls] = super(MetaClass,cls).__call__(*args,**kwargs)
            return cls._instance[cls]

class RabbitMqServerConfigure(metaclass=MetaClass):
    def __init__(self, host="localhost",queue="Class_notification") :
        self.host = host 
        self.queue = queue




class rabbaitmqServer():
    def __init__(self,server):
        self.server = server
        self._connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.server.host))
        self._channel = self._connection.channel()
        self._tem =self._channel.queue_declare(queue='Class_notification')


    def send_email(data):
        import smtplib
        import email.utils
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        SENDER = 'js0002604@gmail.com'
        SENDERNAME = 'Jyoti Sharma'
        RECIPIENT  = 'jyoti_sharma@sggscc.ac.in'
        USERNAME_SMTP = "AKIATOSY6CBGRXS5M247"
        PASSWORD_SMTP = "BEZWCi64AyHVKvNmSyhSKuy+8OXU6aVBbkX3Xox6YwoG"
        HOST = "email-smtp.ap-south-1.amazonaws.com"
        PORT = 587
        SUBJECT = 'Amazon SES Test (Python smtplib)'
        BODY_TEXT = (data)
        BODY_HTML = """<html>
        <head></head>
        <body>
        <h1>Amazon SES SMTP Email Test</h1>
        <p>This email was sent with Amazon SES using the
            <a href='https://www.python.org/'>Python</a>
            <a href='https://docs.python.org/3/library/smtplib.html'>
            smtplib</a> library.</p>
        </body>
        </html>
                    """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = SUBJECT
        msg['From'] = email.utils.formataddr((SENDERNAME, SENDER))
        msg['To'] = RECIPIENT
        part1 = MIMEText(BODY_TEXT, 'plain')
        part2 = MIMEText(BODY_HTML, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Try to send the message.
        try:
            server = smtplib.SMTP(HOST, PORT)
            server.ehlo()
            server.starttls()
            #stmplib docs recommend calling ehlo() before & after starttls()
            server.ehlo()
            server.login(USERNAME_SMTP, PASSWORD_SMTP)
            server.sendmail(SENDER, RECIPIENT, msg.as_string())
            server.close()
        # Display an error message if something goes wrong.
        except Exception as e:
            print ("Error: ", e)
        else:
            print ("Email sent!")
        return 0
    def  compareTime(currentTime,newTime):
        qN=list(map(int,newTime.split(":")))
        qC=list(map(int,currentTime.split(":")))
       # print(qN,qC)
        if qN[0] <= qC[0] + 1:
            return True
        else:
            return False 



    def callback(self,ch,method,properties,body):
        payload = body.decode("utf-8")
        payload =ast.literal_eval(payload)
        print(payload["Notification"])
        dataframe = pd.read_csv("NotificationData.csv")
        serialNo = len(dataframe["SN"])
        connection = mysql.connector.connect(host='localhost',
                                         database='Rabbit',
                                         user='root',
                                         password='admin')
        if connection.is_connected():
            db_Info = connection.get_server_info()
            print("Connected to MySQL Server version ", db_Info)
            cursor = connection.cursor()
            cursor.execute("select database();")
            record = cursor.fetchone()
            print("You're connected to database: ", record)
        cursor.execute("Insert into NotificationRecord (classId,studentId,studentName,notification,sendDate,sendTime,email) values('{}','{}','{}','{}','{}','{}','{}');".format(int(payload["ClassId"]),int(payload["StudentId"]) ,
                             payload["StudentName"], 
                             payload["Notification"],payload["Date"],
                             payload["Time"],"email"))
        
        connection.commit()
        index=0
    
        cursor.execute("Select * from NotificationRecord where sendDate ='2021-05-24';")
        data= cursor.fetchall()
        connection.commit()
        #cursor.execute("delete from NotificationRecord where sendDate ='2021-05-24';")
        #connection.commit()
        print("data read performed: ",data)
        today = datetime.date.today()
        d1 = today.strftime("%Y-%m-%d") 
        que =[]
        sent_no=0
        now = datetime.datetime.now().time()
        currentTime = now.strftime("%H:%M")
        for i in data:
            if rabbaitmqServer.compareTime(currentTime,i[5+1]):
                que.append(i)
        print(que)
        if len(que)>0:
            while len(que)>0:
                send = que.pop()
                rabbaitmqServer.send_email("This is scheduled email : "+str(len(que)))
                cursor.execute("delete from NotificationRecord where sN ='{}';".format(i[0]))
                connection.commit()
                print(len(que))
        

        print("[x] Received %r"%body)


    def startserver(self):
        self._channel.basic_consume(self.server.queue ,on_message_callback=self.callback,auto_ack=True)
        print(' [*] Waiting for message . To exit press CTRl+C')

        self._channel.start_consuming()

if __name__ =="__main__":

    serverconfigure = RabbitMqServerConfigure()
    server = rabbaitmqServer(server= serverconfigure)
    server.startserver()
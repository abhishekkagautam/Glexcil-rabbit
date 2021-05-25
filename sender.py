from pika import channel
from pika.spec import Queue


try :
    import pika
    import pandas

except Exception as e:
    print(e)

class MetaClass(type):
    _instance ={}
    def __call__(cls, *args, **kwargs) :
        if cls not in cls._instance:
            cls._instance[cls] = super(MetaClass,cls).__call__(*args,**kwargs)
            return cls._instance[cls]

class RabbitMq(metaclass=MetaClass):
    def __init__(self,queue='hello') :
        self._connection = pika.BlockingConnection(
                             pika.ConnectionParameters(host="localhost")
                            )
        self._channel =self._connection.channel()
        self.queue  = queue 
        self._channel.queue_declare(queue=self.queue)
    def publish(self,payload={}):
        self._channel.basic_publish(exchange="",
                                    routing_key='hello',
                                    body=str(payload))
        print("Message Published")

        self._connection.close()

if __name__ == "__main__":
    server = RabbitMq(QueueNames)
    server.publish(payload={"Data":"this is second "})

create database Rabbit;
use Rabbit;
create table NotificationRecord ( sN bigint NOT NULL AUTO_INCREMENT, classId bigint,
				studentId bigint,studentName varchar(150),notification varchar(1000),
				sendDate varchar(10), sendTime varchar(12),email varchar(150),
				PRIMARY KEY (sN));

show tables;
select * from NotificationRecord;

Insert into NotificationRecord (classId,studentId,studentName,notification,sendDate,sendTime,email) values(2,1,"kk","dd","24/05/2020","10:00","kll@ll.kk");
Select * from NotificationRecord where sendDate ='2021-05-24';

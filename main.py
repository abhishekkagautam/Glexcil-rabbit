import base64
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
import smtplib
from email.message import EmailMessage
import log
import cv2
import numpy
import datetime
from datetime import date
from instamojo_wrapper import Instamojo
import math
import re

app = Flask(__name__)
app.secret_key = 'secret_key'

app.config.from_object('config')
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth = OAuth(app)
oauth.register(
    name='google',
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid email profile'
    }
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
ALLOWED_EXTENSIONS_VIDEO = {'mp4', 'avi'}

demovideo = ''

def getSlots(TutorId):
    conn, cur= connection()
    cur.execute(
        "SELECT TS.DayId, group_concat(CONCAT(TS.FromTime,'_',TS.SlotId)) as 'Dayslots' FROM tutorslots TS JOIN tutordetails TD on TD.TutorId=TS.TutorId JOIN Days D on D.DayId=TS.DayId WHERE TS.TutorId='{}' GROUP BY D.Dayname".format(
            TutorId))
    slots = cur.fetchall()
    dayid = []
    slot = []
    slotid = []
    for i in range(len(slots)):
        dayid.append(slots[i][0])
        slot.append(slots[i][1])

    sdata = []
    stdata = []
    num = 0
    mlen = 0
    while num <= 6:
        if dayid.count(num) == 1:
            ind = dayid.index(num)
            list = slot[ind].split(',')
            sid = []
            stid = []
            for row in list:
                new = row.split('_')
                sid.append(new[0])
                stid.append(new[1])
            sdata.append(sid)
            stdata.append(stid)
            if len(list) > mlen:
                mlen = len(list)
        else:
            sdata.append([])
            stdata.append([])
        num += 1


    dates = []
    # [[], ['06:00:00'], ['07:00:00', '06:00:00'], [], [], [], []]


    today = date.today()
    curdate= today
    # today = session['today']
    ndate = session['current_date'].split('/')
    ndate = ndate[2]+'-'+ndate[0]+'-'+ndate[1]
    today = datetime.datetime.strptime(ndate, '%Y-%m-%d')

    dates.append(str(today))
    for i in range(6):
        today += datetime.timedelta(days=1)
        dates.append(str(today))

    dateshown = []
    for i in range(len(dates)):
        data = dates[i].split(' ')
        newdate = data[0].split('-')
        str1 = newdate[2]+'/'+newdate[1]
        dateshown.append(str1)
        dates[i] = data[0]

    dayid = curdate.weekday()

    if dayid == 6:
        dayid = 0
    else:
        dayid = dayid + 1

    fl = []
    fc = []
    fs = []

    for i in range(mlen):
        d = ['','','','','','','']
        dc = []
        ds = ['','','','','','','']
        count = 0
        while count < 7:

            el = sdata[dayid]
            es = stdata[dayid]
            if len(el) - 1 < i:
                # d.append('')
                dc.append(0)
            else:

                fdate = str(dates[count]) + ' ' + str(el[i])

                # +10: 00 -> session['tz_offset']
                cur.execute("SELECT CONVERT_TZ('{}','+05:30','{}')".format(fdate, session['tz_offset']))
                res = cur.fetchall()
                newdate = str(res[0][0]).split(' ')
                ndate = datetime.datetime.strptime(newdate[0], '%Y-%m-%d')
                did= ndate.weekday()
                if did == 6:
                    did = 0
                else:
                    did = did + 1

                d[count] = newdate[1]
                ds[count] = es[i]

                cur.execute(
                    "Select SlotId from tutorslots where Tutorid='{}' and FromTime='{}' and DayId='{}'".format(TutorId,
                                                                                                               el[i],
                                                                                                               dayid))

                res = cur.fetchall()

                cur.execute(
                    "select * from trialclasses where TutorId='{}' and Date='{}' and SlotId='{}'".format(TutorId,
                                                                                                         dates[count],
                                                                                                         res[0][0]))
                res = cur.fetchall()

                if res:
                    dc.append(1)
                else:
                    dc.append(0)

            dayid += 1
            if dayid == 7:
                dayid = 0

            count += 1
        fl.append(d)
        fc.append(dc)
        fs.append(ds)

    return fl, fc, fs, dates, dateshown


# Send mail
def send_email(subject, to, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = "blackconsoletraining@gmail.com"
    msg['To'] = to
    body1 = body
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login("blackconsoletraining@gmail.com", "dzsjkqyouhyckxsn")
        smtp.send_message(msg)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_file_video(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS_VIDEO


# mysql connection
def connection():
    conn = mysql.connector.connect(host="localhost",port="3306", user="root", database="GLIXCEL_DB", password="admin",
                                   buffered=True)
    cur = conn.cursor()
    return conn, cur


def findDayId(day):
    if day == 'Sunday':
        return 0
    elif day == 'Monday':
        return 1
    elif day == 'Tuesday':
        return 2
    elif day == 'Wednesday':
        return 3
    elif day == 'Thursday':
        return 4
    elif day == 'Friday':
        return 5
    elif day == 'Saturday':
        return 6


def getstaticdata():
    conn, cur = connection()
    cur.execute("Select * from country")
    countries = cur.fetchall()
    cur.execute("Select * from languages")
    languages = cur.fetchall()
    cur.execute("Select * from timezone")
    timezone = cur.fetchall()
    cur.execute("Select * from currency")
    currency = cur.fetchall()
    cur.execute("Select SkillId, SkillName from skills")
    skills = cur.fetchall()
    cur.execute("Select * from days")
    days = cur.fetchall()
    return countries, languages, timezone, currency, skills, days


# login function
@log.log_error()
@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('index.html')


# login function
@log.log_error()
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        details = request.form
        email = details['email']
        password = details['password']
        conn, cur = connection()

        cur.execute(
            "Select HrId from hrlogin where Email='{}' and CAST(AES_DECRYPT(Password, 'glixceldb') AS CHAR(50))='{}'".format(
                email, password
            ))
        res = cur.fetchall()
        if res != () and res != []:
            session['id'] = res[0][0]
            session['role'] = 'hr'
            session['email'] = email
            return redirect(url_for('hr_tutor_registration'))

        cur.execute(
            "Select AdminId from adminlogin where Email='{}' and CAST(AES_DECRYPT(Password, 'glixceldb') AS CHAR(50))='{}'".format(
                email, password
            ))
        res = cur.fetchall()
        if res != () and res != []:
            session['id'] = res[0][0]
            session['role'] = 'admin'
            session['email'] = email
            return redirect(url_for('admin_show_all_profile'))

        cur.execute(
            "Select StudentId from studentlogin where Email='{}' and CAST(AES_DECRYPT(Password, 'glixceldb') AS CHAR(50))='{}'".format(
                email, password
            ))
        res = cur.fetchall()

        if res != () and res != []:
            session['id'] = res[0][0]
            session['role'] = 'student'
            session['email'] = email

            return redirect('tutor_search')

        cur.execute(
            "Select TutorId from tutorlogin where Email='{}' and CAST(AES_DECRYPT(Password, 'glixceldb') AS CHAR(50))='{}'".format(
                email, password
            ))
        res = cur.fetchall()

        if res != () and res != []:

            session['id'] = res[0][0]
            session['role'] = 'tutor'
            session['email'] = email
            return redirect(url_for('tutor_dashboard'))

        else:
            msg1 = "Wrong Id or Password"
            return render_template('login.html', msg1=msg1)

    return render_template('login.html')


@log.log_error()
@app.route('/logout')
def logout():
    session.pop('id', None)
    session.pop('role', None)
    session.pop('email', None)

    return redirect('/')

# tutor registration done by rishabh
# tutor registration
# tutor registration
@log.log_error()
@app.route('/register', methods=['GET', 'POST'])
def register():
    # if session['role'] == 'tutor':
    if request.method == 'GET':
        conn, cur = connection()
        cur.execute("Select * from country")
        countries = cur.fetchall()
        cur.execute("Select * from languages")
        languages = cur.fetchall()
        cur.execute("Select * from timezone")
        timezone = cur.fetchall()
        cur.execute("Select * from currency")
        currency = cur.fetchall()
        cur.execute("Select SkillId, SkillName from skills")
        skills = cur.fetchall()
        return render_template('register.html', countries=countries, languages=languages, timezone=timezone,
                               currency=currency,
                               skills=skills)
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['Name']
        contact = request.form['phno']
        curr = request.form['currency']
        languages = request.form.getlist('framework[]')
        timezonename = request.form['zones']
        fromhour = request.form['fromhour']
        tohour = request.form['tohour']
        headline = request.form['headline']
        desc = request.form['desc']
        country = request.form['country']
        #levels = request.form['levels']
        #skills = request.form['skills']
        headline = headline.replace("'", "''")
        desc     = desc.replace("'", "''")
        url = request.form['url']
        skills = request.form.getlist('skills[]')
        tags = request.form.getlist('tags[]')
        print(skills,"skills")
        print(tags,"tags")

        conn, cur = connection()
        # for s in range(len(skills)):
        #     print(skills[s],tags[s])

            # cur.execute("Select TagId from tags where TagName='{}'".format(skill_list[i]))
            # res = cur.fetchall()




        language = ''
        tname = name
        for i in range(len(languages)):
            if i == 0:
                language = languages[i]
            else:
                language = language + ',' + languages[i]
        raterange = str(fromhour) + '-' + str(tohour)
        #skill = []
        level = []
        #tags = []
        # skill_list = skills.split(',')
        # level_list = levels.split(',')
        conn, cur = connection()
        # for i in range(len(skill_list)):
        #     skill.append(skill_list[i])
        #     level.append(tags[i])
        #     cur.execute("Select TagId from tags where SKillId='{}'".format(skill_list[i]))
        #     res = cur.fetchall()
        #     str1 = ''
        #     for i in range(len(res)):
        #         if i == 0:
        #             str1 = str(res[i][0])
        #         else:
        #             str1 = str1 + ',' + str(res[i][0])
        #     tags.append(str1)
        photo = request.files['pic']
        url = request.form['url']
        countries, languages, timezone, currency, skill,  days = getstaticdata()
        cur.execute(
            "Insert into tutordetails(Name, Email, Contact, Country, Languages, TimezoneName, HourlyRateRange, Headline, Description, Currency) values('{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')".format(
                name, email, contact, country, language, timezonename, raterange, headline, desc, curr
            ))
        conn.commit()
        cur.execute("Select LAST_INSERT_ID() from tutordetails")
        tutorid = cur.fetchall()
        filename = secure_filename(photo.filename)
        ext = filename.split('.')
        name = str(tutorid[0][0]) + '.' + ext[len(ext) - 1]
        photo.save(os.path.join(os.getcwd() + '/static/tutorimages', name))
        cur.execute("Update tutordetails set Image='{}' where TutorId='{}'".format(name, tutorid[0][0]))
        conn.commit()
        # global demovideo
        # path = os.getcwd() + '/static/demovideo/' + str(tutorid[0][0]) + '.mp4'
        # fh = open(path, "wb")
        # fh.write(base64.b64decode(demovideo))
        # fh.close()
        # name = str(tutorid[0][0]) + '.mp4'
        cur.execute("Update tutordetails set DemoVideo='{}' where TutorId='{}'".format(url, tutorid[0][0]))
        conn.commit()
        demovideo = ''
        for i in range(len(skills)):
            # print(
            #     "Insert into tutorskills(TutorId, SkillId, TagId,  CostPerHour) values('{}','{}','{}', 0)".format(
            #         tutorid[0][0], skills[i], tags[i]))
            LevelId=2
            cur.execute("Insert into tutorskills(TutorId, SkillId, TagId,  CostPerHour) values('{}','{}','{}',100)".format(
                    tutorid[0][0], skills[i], tags[i]))
            conn.commit()
        subject = 'Registration done successfully!!'
        to = email
        body1 = 'Congratulations ' + str(tname) + ','
        body2 = 'Your application has been submitted successfully!! '
        body3 = 'We will review your application and get back to you after screening of your application within 48 hours.'
        body4 = 'Email: ' + email
        body = "{}\n{}\n{}\n{}\n".format(body1, body2, body3, body4)
        send_email(subject, to, body)
        flash('You are successfully registered!!')
        flash("Success")
        flash("success")
        return render_template('register.html', countries=countries, languages=languages, timezone=timezone,
                               currency=currency,
                               skills=skills)
        

# sign up with google
@log.log_error()
@app.route('/signupwithgoogle', methods=['GET', 'POST'])
def signupwithgoogle():
    redirect_uri = url_for('auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


# google authentication
@log.log_error()
@app.route('/auth')
def auth():
    token = oauth.google.authorize_access_token()
    user = oauth.google.parse_id_token(token)
    if user['email_verified'] != True:
        msg1 = "Wrong Id or Password"
        return render_template('student_registration.html', msg=msg1)

    conn, cur = connection()
    cur.execute("Select * from studentlogin where Email='{}'".format(user['email']))
    res = cur.fetchall()
    if res == () or res == []:
        cur.execute("Insert into studentlogin(Name, Email) values('{}','{}')".format(user['name'], user['email']))
        conn.commit()
        msg1 = "You are successfully registered!!"
        return render_template('student_registration.html', msg=msg1)
    else:
        msg1 = "Email already exists!!"
        return render_template('student_registration.html', msg=msg1)


@log.log_error()
@app.route('/loginwithgoogle', methods=['GET', 'POST'])
def loginwithgoogle():
    redirect_uri = url_for('loginauth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


# google authentication
@log.log_error()
@app.route('/loginauth')
def loginauth():
    token = oauth.google.authorize_access_token()
    user = oauth.google.parse_id_token(token)
    if user['email_verified'] != True:
        msg1 = "Wrong Id or Password"
        return render_template('login.html', msg1=msg1)

    conn, cur = connection()
    cur.execute("Select * from studentlogin where Email='{}'".format(user['email']))
    res = cur.fetchall()
    session['id'] = res[0][0]
    session['role'] = 'student'
    session['email'] = res[0][2]
    return redirect('tutor_search')


# student registration form
@log.log_error()
@app.route('/studentregister', methods=['GET', 'POST'])
def studentregister():
    if request.method == 'POST':
        details = request.form
        email = details['student_email']
        name = details['student_name']
        password = details['password']
        confirm_password = details['confirm_password']
        if password != confirm_password:
            return render_template('student_registration.html', msg='Incorrect password!!')

        conn, cur = connection()

        cur.execute(
            "Insert into studentlogin(name, email, password) values('{}','{}',aes_encrypt('{}', 'glixceldb'))".format(
                name, email, password
            ))
        conn.commit()
        flash('You are successfully registered!!')
        flash("Success")
        flash("success")
        return render_template('student_registration.html')
    else:
        return render_template('student_registration.html')

@log.log_error()
@app.route('/checkmail', methods=['GET', 'POST'])
def checkmail():
    email = request.form['email']
    conn, cur = connection()
    cur.execute("Select TutorId from tutorlogin where Email='{}'".format(email))
    res = cur.fetchall()
    if res == () or res == []:
        cur.execute("Select StudentId from studentlogin where Email='{}'".format(email))
        res = cur.fetchall()
        if res == () or res == []:
            cur.execute("Select TutorId from tutordetails where Email='{}' and Approved is null".format(email))
            res = cur.fetchall()
            if res == () or res == []:
                msg = 'empty'
            else:
                msg = 'exists'
        else:
            msg = 'exists'
    else:
        msg = 'exists'

    return jsonify({'res': msg})

@log.log_error()
@app.route('/countrywisedata', methods=['GET', 'POST'])
def countrywisedata():
    country = request.form['country']
    conn, cur = connection()
    cur.execute("Select CountryName, CountryIso, CountryIsdCode from country where CountryId='{}'".format(country))
    countrydata = cur.fetchall()

    cur.execute("Select * from currency where country = '{}'".format(countrydata[0][0]))
    currencydata = cur.fetchall()
    if currencydata:
        currencydata = currencydata[0][2]
    else:
        currencydata = 'not'
    return jsonify(
        {'name': countrydata[0][0], 'iso': countrydata[0][1], 'isd': countrydata[0][2], 'currencydata': currencydata})

@log.log_error()
@app.route('/skillsdata', methods=['GET', 'POST'])
def skillsdata():
    conn, cur = connection()
    cur.execute("Select SkillId, SkillName from skills")
    skillid = []
    skillname = []
    skills = cur.fetchall()
    if skills != () and skills != []:
        for i in range(len(skills)):
            skillid.append(skills[i][0])
            skillname.append(skills[i][1])
    return jsonify({'skillid': skillid, 'skillname': skillname})

@log.log_error()
@app.route("/admin_show_all_profile", methods=['GET', 'POST'])
def admin_show_all_profile():
    if 'id' in session:
        if session['role'] == 'admin':
            conn, cur = connection()
            cur.execute("SELECT * FROM `tutordetails` where Approved is null")
            tutor_data = cur.fetchall()
            totaltutor = len(tutor_data)
            return render_template('admin_first_page.html', tutor_data=tutor_data, totaltutor=totaltutor)
    return redirect('/')


@app.route("/admin_view_profile/<int:TutorId>", methods=['GET', 'POST'])
def admin_view_profile(TutorId):
    if 'id' in session:
        if session['role'] == 'admin':
            if request.method == "GET":
                conn, cur = connection()
                cur.execute("SELECT * FROM `tutordetails` WHERE TutorId='{}'".format(TutorId))
                tutor_data = cur.fetchone()

                cur.execute("Select CountryName from country where CountryId='{}'".format(tutor_data[4]))
                res = cur.fetchall()
                country = res[0][0]
                cur.execute("Select symbol from currency where code='{}'".format(tutor_data[15]))
                res = cur.fetchall()
                symbol = res[0][0]
                cur.execute(
                    "SELECT t.TutorId,s.SkillName FROM `tutorskills` t left JOIN tutordetails td on td.TutorId =t.TutorId left JOIN skills s on s.SkillId =t.SkillId WHERE t.TutorId='{}'".format(
                        TutorId))
                skill_data = cur.fetchall()

                return render_template('admin_section_profile.html', tutor_data=tutor_data, skill_data=skill_data,
                                       symbol=symbol, country=country)

            if request.method == "POST":
                Approved = request.form['Approved']
                conn, cur = connection()
                cur.execute("UPDATE tutordetails SET Approved='{}' WHERE TutorId='{}'".format(Approved, TutorId))
                conn.commit()

                cur.execute("select md5(tutorid), email, name from tutordetails where tutorid='{}'".format(TutorId))
                data = cur.fetchall()
                if int(Approved) == 1:
                    cur.execute(
                        "Insert into tutorlogin(TutorId, Email, Password) values('{}','{}',aes_encrypt('{}', 'glixceldb'))".format(
                            TutorId, data[0][1], data[0][0]
                        ))
                    conn.commit()

                    subject = 'Profile approved!!'
                    to = data[0][1]
                    body1 = 'Congratulations ' + str(data[0][2]) + ','
                    body2 = 'Your application has been approved successfully!! '
                    body3 = 'Your login credentials are :'
                    body4 = 'Email: ' + data[0][1]
                    body5 = 'Password: ' + data[0][0]
                    body = "{}\n{}\n{}\n{}\n{}\n".format(body1, body2, body3, body4, body5)
                    send_email(subject, to, body)
                    flash('Profile Accepted successfully!!')
                    flash("Success")
                    flash("success")
                    return redirect(url_for('admin_show_all_profile'))
                else:
                    subject = 'Profile rejected!!'
                    to = data[0][1]
                    body1 = 'Hello ' + str(data[0][2]) + ','
                    body2 = 'We regret to inform you that your application has been rejected!! '
                    body = "{}\n{}\n".format(body1, body2)
                    send_email(subject, to, body)
                    flash('Profile Rejected successfully!!')
                    flash("Rejected")
                    flash("error")
                    return redirect(url_for('admin_show_all_profile'))
    return redirect('/')


@app.route("/editable_profile", methods=['GET', 'POST'])
def editable_profile():
    if 'id' in session:
        if session['role'] == 'tutor':
            if request.method == 'GET':
                conn, cur = connection()
                cur.execute("Select * from tutordetails where TutorId='{}'".format(session['id']))
                tutordata = cur.fetchall()
                cur.execute(
                    "SELECT t.TutorId,s.SkillName, t.CostPerHour, t.SkillId,t.TagId FROM `tutorskills` t left JOIN tutordetails td on td.TutorId =t.TutorId left JOIN skills s on s.SkillId =t.SkillId  WHERE t.TutorId='{}'".format(
                        session['id']))
                skill_data = cur.fetchall()

                countries, languages, timezone, currency, skills, days = getstaticdata()
                cur.execute("Select SkillId, SkillName from skills")
                allskills = cur.fetchall()

                #fetch all tutor skills
                print(skill_data,"skill_data")
                skill_data_len = len(skill_data)
                return render_template('editable_profile.html',allskills=allskills, tutordata=tutordata[0], skill_data=skill_data,
                                       countries=countries,skill_data_len=skill_data_len,
                                       languages=languages, timezone=timezone, currency=currency, skills=skills)

            return render_template('editable_profile.html')
    return redirect('/')



@app.route('/editdetails', methods=['GET', 'POST'])
def editdetails():
    if request.method == 'POST':
        headline = request.form['headline']
        description = request.form['description']
        description= description.replace("'","").replace('"', '')
        phoneno = request.form['phone']
        timezone = request.form['zone']
        country = request.form['country']
        currency = request.form['currency']

        conn, cur = connection()
        cur.execute(
            "UPDATE tutordetails SET headline ='{}',description='{}',Contact='{}',country='{}',timezonename='{}', currency='{}' where TutorId='{}'".format(
                headline, description, phoneno, country, timezone, currency,session['id']
            ))
        conn.commit()
    return jsonify({'res': 'done'})


@app.route('/editskills', methods=['GET', 'POST'])
def editskills():
    if request.method == 'POST':
        skills = request.form.getlist('skills[]')
        tags = request.form.getlist('tags[]')
        cost = request.form.getlist('costdata[]')
        conn, cur = connection()
        print(skills,"skills")
        print(tags,"tags")
        print(cost,"cost")
        print(len(skills),"cost")
        cur.execute("Delete from tutorskills where TutorId='{}'".format(session['id']))
        conn.commit()

        for i in range(len(skills)):
            if skills[i]!='':
                cur.execute(
                    "Insert into tutorskills(TutorId, SkillId, TagId, CostPerHour) values('{}','{}','{}','{}')".format(
                        session['id'], skills[i] ,tags[i], cost[i]
                    ))
                conn.commit()

    return redirect('/editable_profile')

#@app.route('/editslots', methods=['GET', 'POST'])


# def editslots():
#     if request.method == 'POST':
#         daydata = request.form['daydata']
#         fromdata = request.form['fromdata']
#         todata = request.form['todata']
#         daylist = daydata.split(',')
#         fromlist = fromdata.split(',')
#         tolist = todata.split(',')
#         conn, cur = connection()
#         cur.execute(
#             "Delete from tutorslots where SlotId NOT IN (Select slotId from trialclasses where tutorId='{}') AND TutorId='{}'".format(
#                 session['id'], session['id']))
#         conn.commit()
#         for i in range(len(daylist)):
#             if daylist[i]!='':
#                 cur.execute("Select * from tutorslots where TutorId='{}' and DayId='{}' and FromTime='{}' and ToTime='{}'".format(
#                     session['id'], daylist[i], fromlist[i], tolist[i]
#                 ))
#                 res = cur.fetchall()
#                 if res==[] or res==():
#                     cur.execute("Insert into tutorslots(TutorId, DayId, FromTime, ToTime) values('{}','{}','{}','{}')".format(
#                         session['id'], daylist[i], fromlist[i], tolist[i]
#                     ))
#                     conn.commit()

#     return jsonify({'res': 'done'})



def fd(photo):
    photodetect = photo.read()
    face_cascade = cv2.CascadeClassifier('face_detector.xml')
    npimg = numpy.fromstring(photodetect, numpy.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    faces = face_cascade.detectMultiScale(img, 1.1, 4)
    if faces == () or len(faces) > 1:
        msg = "no"
        flash("No Face is detected")
        flash("Warning")
        flash("warning")
        return redirect(url_for('editable_profile'))
    return 'ok'

@app.route('/editpic', methods=['GET', 'POST'])
def editpic():
    if request.method == 'POST':
        photo = request.files['pic']


        conn, cur = connection()

        if not (photo and allowed_file(photo.filename)):
            flash("Only 'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif' files allowed!!!")
            flash("Warning")
            flash("warning")
            return redirect(url_for('editable_profile'))

        # res = fd(photo)

        filename = secure_filename(photo.filename)
        ext = filename.split('.')
        name = str(session['id']) + '.' + ext[len(ext) - 1]
        print(photo)
        photo.save(os.path.join(os.getcwd() + '/static/tutorimages', name))
        cur.execute("Update tutordetails set Image='{}' where TutorId='{}'".format(name, session['id']))
        conn.commit()

        # filename = secure_filename(video.filename)
        # ext = filename.split('.')
        # name = str(session['id']) + '.' + ext[len(ext) - 1]
        # video.save(os.path.join(os.getcwd() + '\\static\\demovideo', name))
        # cur.execute("Update tutordetails set DemoVideo='{}' where TutorId='{}'".format(name, session['id']))
        # conn.commit()

    flash("Pic Changed Successfully")
    flash("Success")
    flash("success")
    return redirect(url_for('editable_profile'))

@app.route('/editpwd', methods=['GET', 'POST'])
def editpwd():
    if request.method == 'POST':
        pwd = request.form['pwd']
        conpwd = request.form['conpwd']

        conn, cur = connection()
        cur.execute(
            "Select CAST(AES_DECRYPT(Password, 'glixceldb') AS CHAR(50)) from tutorlogin where TutorId='{}'".format(
                session['id']
            ))
        password = cur.fetchall()
        if password[0][0] != pwd:
            return jsonify({'res': 'no'})
        cur.execute("Update tutorlogin set Password = aes_encrypt('{}', 'glixceldb') where TutorId='{}'".format(conpwd,
                                                                                                                session[
                                                                                                                    'id']))
        conn.commit()
    return jsonify({'res': 'done'})

@app.route('/editvideo', methods=['GET', 'POST'])
def editvideo():
    if request.method == 'POST':
        # photo = request.files['pic']
        video = request.form['demovideo']
        # photodetect = photo.read()
        conn, cur = connection()

        # if not (video and allowed_file_video(video.filename)):
        #     flash("Only 'mp4', 'avi' files allowed!!!")
        #     flash("Warning")
        #     flash("warning")
        #     # return jsonify({'res': msg})
        #     return redirect(url_for('editable_profile'))

        # filename = secure_filename(video.filename)
        # ext = filename.split('.')
        # name = str(session['id']) + '.' + ext[len(ext) - 1]
        # video.save(os.path.join(os.getcwd() + '\\static\\demovideo', name))
        cur.execute("Update tutordetails set DemoVideo='{}' where TutorId='{}'".format(video , session['id']))
        conn.commit()

    # return jsonify({'res':'done'})
    flash("Demo Link Updateed Successfully")
    flash("Success")
    flash("success")
    return redirect(url_for('editable_profile'))




@app.route("/editable_profile_json", methods=['GET', 'POST'])
def editable_profile_json():
    conn, cur = connection()
    # session['id'] = 1
    cur.execute(
        "SELECT t.TutorId,s.SkillName, t.CostPerHour, t.SkillId FROM `tutorskills` t left JOIN tutordetails td on td.TutorId =t.TutorId left JOIN skills s on s.SkillId =t.SkillId  WHERE t.TutorId='{}'".format(
            session['id']))
    skill_data = cur.fetchall()
    countries, languages, timezone, currency, skills, days = getstaticdata()
    # cur.execute(
    #     "SELECT ts.TutorId,ts.DayId, ts.SlotId, convert(ts.FromTime, char), convert(ts.ToTime, char) FROM `tutorslots` ts WHERE ts.TutorId='{}'".format(
    #         session['id']))
    cur.execute("SELECT TS.TutorId,TS.DayId, TS.SlotId, convert(TS.FromTime, char), convert(TS.ToTime, char) FROM `tutorslots` TS WHERE TS.SlotId NOT IN (Select SlotId from trialclasses where tutorId = '{}') AND TS.SlotId NOT IN(SELECT TSH.Slotid from tutorschedule TSH JOIN trialclasses TC ON TSH.TrialClassId = TC.TrialClassId WHERE TutorId = '{}') AND TS.TutorId='{}'".format(
           session['id'], session['id'], session['id']))
    slot_data = cur.fetchall()
    print(slot_data)
    return jsonify(
        {'countries': countries, 'languages': languages, 'timezone': timezone, 'currency': currency, 'skills': skills,
         'skill_data': skill_data, 'days': days, 'slot_data': slot_data})



@app.route("/demovideo", methods=['GET', 'POST'])
def demovideo():
    return render_template('demovideopage.html')

@app.route('/blobobj', methods=['GET', 'POST'])
def blobobj():
    blobobj = request.files['source']
    base = base64.encodebytes(blobobj.read())
    global demovideo
    demovideo = base
    # path = os.getcwd() +'\\static\\video.mp4'
    # fh = open(path, "wb")
    # fh.write(base64.b64decode(base))
    # fh.close()
    return jsonify({'res': 'done'})


@app.route("/facedetection", methods=['GET', 'POST'])
def facedetection():
    photo = request.files['photo']
    if not (photo and allowed_file(photo.filename)):
        msg = "invalid"
        return jsonify({'res': msg})
    photodetect = photo.read()
    face_cascade = cv2.CascadeClassifier('face_detector.xml')
    npimg = numpy.fromstring(photodetect, numpy.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    faces = face_cascade.detectMultiScale(img, 1.1, 4)
    if faces == () or len(faces) > 1:
        msg = "no"
    else:
        msg = 'yes'
    return jsonify({'res': msg})




#added by rishabh 6-6-2021
@app.route("/tutor/<tname>/<sname>", methods=['GET', 'POST'])
def tutor(tname, sname):
    conn, cur = connection()
    cur.execute("Select TutorId from tutordetails where Name = '{}'".format(tname))
    res = cur.fetchall()
    TutorId = res[0][0]
    cur.execute("Select SkillId from skills where SkillName = '{}'".format(sname))
    res = cur.fetchall()
    SkillId = res[0][0]
    cur.execute("""SELECT t.TutorId,t.Name,t.Email, t.Contact, t.Country, t.Languages, t.TimezoneName, t.HourlyRateRange, t.Headline, t.Description, t.Image, t.DemoVideo, c.CountryName From tutordetails t
    inner join country c on c.CountryId = t.Country WHERE t.Tutorid='{}'""".format(TutorId))
    data = cur.fetchone()



    cur.execute('select  t.TutorId, s.SkillName, t.TagId,t.CostPerHour from tutorskills t inner join skills s on t.SkillId = s.SkillId where TutorId="{}"'.format(TutorId))
    skill = cur.fetchall()
    skillname = skill[0][0]
    costperhour = skill[0][3]
    skill_list = []
    taglist = []
    costperhour_list = []
    for s in range(len(skill)):
        skill_list.append(skill[s][1])
        list1 = skill[s][2].split(',')
        taglist.append(list1)
        costperhour_list.append(skill[s][3])
   
    
    # for s in skillname:
    #     cur.execute(
    #     "Select TagId, CostPerHour from tutorskills where TutorId='{}' and SkillId='{}'".format(TutorId, skill[s][]))
    #     tags = cur.fetchall()
    #     costperhour = tags[0][1]
    #     list = tags[0][0].split(',')
    #     tagsdata = []

    # for i in list:
    #     print(i,"1064")
    #     cur.execute("Select TagName from tags where TagId='{}'".format(i))
    #     res = cur.fetchall()
    #     tagsdata.append(res[0][0])

    fl, fc, fs, dates, dateshown = getSlots(TutorId)
    flen = len(fl)
    skill_list_len = len(skill_list)
    print(skill_list,taglist,"1069",costperhour,TutorId)
    return render_template('tutor.html',costperhour_list=costperhour_list,TutorId=TutorId,flen=flen, data=data, skillname=skill, costperhour=costperhour, 
                           dates=dates, fl=fl, fc=fc,dateshown=dateshown,
                            SkillId=SkillId,skill_list=skill_list,taglist=taglist,skill_list_len=skill_list_len)



@app.route("/trialpayment", methods=['GET', 'POST'])
def trialpayment():
    tid = session['tid']
    cost = session['tcost']
    date = session['trialdate']
    slotid = session['slotid']
    skillid = session['skillid']
    API_KEY = "ee4efa380b3d757c67d903028468e0b9"
    AUTH_TOKEN = "4242662ab0dfacef442a7cf5f8d9f4f6"
    api = Instamojo(api_key=API_KEY, auth_token=AUTH_TOKEN)

    response = api.payment_request_create(
        amount=cost,
        purpose="Book Trial Class",
        # buyer_name=session['email'],
        send_email=True,
        email=session['email'],
        redirect_url="http://127.0.0.1:5000/after_payment_booktrial"
    )
    conn, cur = connection()
    cur.execute("Insert into paymentdetails(PaymentRequestId, Datetime, Status) values('{}',now(),'Pending')".format(
        response['payment_request']['id']
    ))
    conn.commit()

    cur.execute(
        "Insert into trialclasses(StudentId, TutorId, SkillId, Date, SlotId, PaymentRequestId) values('{}', '{}', '{}', '{}', '{}', '{}')".format(
            session['id'], tid, skillid, date, slotid, response['payment_request']['id']
        ))
    conn.commit()

    return redirect(response['payment_request']['longurl'])


@app.route("/after_payment_booktrial", methods=['GET', 'POST'])
def after_payment_booktrial():
    payment_id = request.args.get('payment_id')
    payment_status = request.args.get('payment_status')
    payment_request_id = request.args.get('payment_request_id')
    email = request.args.get('email')
    conn, cur = connection()
    cur.execute(
        "UPDATE paymentdetails SET Status='{}', PaymentId='{}' where PaymentRequestId='{}'".format(
            payment_status,
            payment_id, payment_request_id))
    conn.commit()

    if payment_status != 'Credit':
        subject = 'Trial Class Booked Successfully!!'
        to = email
        body1 = 'Congratulations ' + ','
        body2 = 'Your payment has been done successfully!! '
        body = "{}\n{}\n".format(body1, body2)
        send_email(subject, to, body)
    else:
        subject = 'Payment Failed!!'
        to = email
        body1 = 'Your payment is failed. Please try again!! '
        body = "{}\n{}\n".format(body1)
        send_email(subject, to, body)

    return redirect(url_for('tutor'))


@app.route("/tutor_search",defaults={'page':1}, methods=['GET', 'POST'])
@app.route("/page/<int:page>", methods=['GET', 'POST'])
def tutor_search(page):
    if request.method == 'GET':
        limit = 2
        offset = page * limit - limit
        conn, cur = connection()
        cur.execute("SELECT * FROM `tutordetails` WHERE Approved=1")
        cur.fetchall()
        total_row = cur.rowcount
        #print("Total Row")
        totalpage = math.ceil(total_row / limit)
        #print('totalpage', totalpage)
        next_page = page + 1
        prev = page - 1
        cur.execute("""SELECT t.TutorId,t.Name,t.Email, t.Contact, t.Country, t.Languages, t.TimezoneName, t.HourlyRateRange, t.Headline, t.Description, t.Image, t.DemoVideo, t.Wallet , t.IsdCode, t.Currency,c.CountryName From tutordetails t
                    inner join country c on c.CountryId = t.Country
                    WHERE Approved=1 ORDER BY Tutorid DESC LIMIT %s OFFSET %s""",
                    (limit, offset))
        data = cur.fetchall()
        #print(data)

        fdata = []
        for row in data:
            row = list(row)
            cur.execute("Select * from tutorskills where tutorid='{}'".format(row[0]))
            skills = cur.fetchall()
            #print("Select * from tutorskills where tutorid='{}'".format(row[0]))
            cur.execute("Select SkillName from skills where SkillId='{}'".format(skills[0][1]))
            sn = cur.fetchall()
            skillname = sn[0][0]
            slist = skills[0][2].split(',')
            print(slist,"1080")
            tlist = []
            # for i in slist:
            #     if i != '':
            #         print("Select TagName from tags where TagName='{}'".format(i))
            #         print("**************************************************")
            #         cur.execute("Select TagName from tags where TagName='{}'".format(i))
            #         tn = cur.fetchall()
            #         tlist.append(tn[0][0])

            row[12] = skills[0][1]
            #print(row[12],"row[12]1100",skills)
            row[13] = skillname
            row[14] = tlist
            row[7] = skills[0][3]
            #print(row[7],"row[7]",row[7])

            cur.execute(
                "SELECT TS.DayId, group_concat(CONCAT(TS.FromTime)) as 'Dayslots' FROM tutorslots TS JOIN tutordetails TD on TD.TutorId=TS.TutorId JOIN Days D on D.DayId=TS.DayId WHERE TS.TutorId='{}' GROUP BY D.Dayname".format(
                    row[0]))
            slots = cur.fetchall()
            #print(slots,"slots")
            if slots:
                dayid = []
                slot = []
                for i in range(len(slots)):
                    dayid.append(slots[i][0])
                    list1 = slots[i][1].split(':')
                    del list1[-1]
                    str1 = ''
                    for i in range(len(list1)):
                        if i == 0:
                            str1 = list1[i]
                        else:
                            str1 = str1 + ':' + list1[i]

                    slot.append(str1)

                sdata = []
                num = 0
                while num <= 6:
                    if dayid.count(num) == 1:
                        ind = dayid.index(num)
                        slist = slot[ind].split(',')
                        sdata.append(slist)
                    else:
                        sdata.append([])
                    num += 1
                row[6] = sdata
            else:
                row[6] = [[], [], [], [], [], [], []]

            fl, fc, fs, dates, dateshown = getSlots(row[0])
            row.append(fl)
            row.append(fc)
            row.append(fs)
            row.append(dates)
            row.append(dateshown)
            fdata.append(row)

        #print(fl, fc, fs, dates, dateshown,"fl, fc, fs, dates, dateshown")
        flen = len(fdata)
        #print(fdata,"fdata")
        countries, languages, timezone, currency, skills, days = getstaticdata()
        return render_template('tutor-search.html', fdata=fdata, flen=flen, skills=skills,page=totalpage,next_page=next_page,prev=prev)

    if request.method == 'POST':
        skill = request.form['skill']
        # raterange = request.form['range']
        # rangerate = raterange.split('-')
        conn, cur = connection()
        # cur.execute(
        #     "SELECT TutorId from tutorskills WHERE SkillId='{}' and CostPerHour between '{}' and '{}'".format(skill,
        #                                                                         rangerate[0],rangerate[1]))
        cur.execute(
            "SELECT tl.TutorId from tutorskills ts , tutorlogin tl WHERE ts.SkillId='{}' and tl.TutorId=ts.TutorId".format(skill))

        res = cur.fetchall()
        fdata = []
        limit=2
        offset=page*limit-limit
        for i in range(len(res)):
            cur.execute("SELECT * From tutordetails WHERE TutorId='{}'".format(res[i]))
            cur.fetchall()
            total_row = cur.rowcount
            print("total row", total_row)
            totalpage = math.ceil(total_row / limit)
            next_page = page + 1
            prev = page - 1
            cur.execute("SELECT * From tutordetails WHERE TutorId='{}' ORDER BY Tutorid DESC LIMIT 2 OFFSET 0".format(
                res[i][0]))
            data = cur.fetchall()
            print(data)
            print("total page data", totalpage)

            # cur.execute("SELECT * From tutordetails WHERE TutorId='{}'".format(res[i][0]))
            # data = cur.fetchall()
            #            cur.execute("SELECT * From tutordetails WHERE TutorId='{}'".format(res[i]))
            #            cur.fetchall()
            #            total_row=cur.rowcount
            #            totalpage=math.ceil(total_row/limit)
            #            next_page=page+1
            #            prev=page-1
            #            cur.execute("SELECT * From tutordetails WHERE TutorId='{}' ORDER BY Tutorid DESC LIMIT 2 OFFSET 0".format(res[i][0]))
            #            data = cur.fetchall()

            for row in data:
                row = list(row)
                cur.execute("Select * from tutorskills where tutorid='{}' and SKillId='{}'".format(row[0], skill))
                skills = cur.fetchall()
                cur.execute("Select SkillName from skills where SkillId='{}'".format(skill))
                sn = cur.fetchall()
                skillname = sn[0][0]
                slist = skills[0][2].split(',')
                # tlist = []
                # for i in slist:
                #     cur.execute("Select TagName from tags where TagName='{}'".format(i))
                #     tn = cur.fetchall()
                #     tlist.append(tn[0][0])

                row[12] = skills[0][1]
                row[13] = skillname
                # row[14] = tlist
                row[7] = skills[0][3]
                fl, fc, fs, dates, dateshown = getSlots(row[0])
                row.append(fl)
                row.append(fc)
                row.append(fs)
                row.append(dates)
                row.append(dateshown)


                fdata.append(row)


        try:
            flen = len(fdata)
            page = totalpage
            next_page = next_page
            prev = prev
            countries, languages, timezone, currency, skills, days = getstaticdata()
            print(fdata)
            return render_template('tutor-search.html',post_skill=int(skill), fdata=fdata, flen=flen, skills=skills, page=page,
                                   next_page=next_page, prev=prev)
        except:
            return redirect('/tutor_search')


@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
    return render_template('student-dashboard.html')


@app.route('/student_trial_view/<id>', methods=['GET', 'POST'])
def student_trial_view(id):
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()
            cur.execute("Select * from trialClasses where TrialClassId='{}'".format(id))
            res = cur.fetchall()
            cur.execute("Select Name from tutordetails where TutorId='{}'".format(res[0][2]))
            tn = cur.fetchall()
            cur.execute("Select SkillName from skills where SkillId='{}'".format(res[0][3]))
            sn = cur.fetchall()
            cur.execute("Select FromTime from tutorslots where SlotId='{}'".format(res[0][6]))
            ft = cur.fetchall()
            tname = tn[0][0]
            sname = sn[0][0]
            fromtime = ft[0][0]
            date = res[0][5]
            link = res[0][9]
            return render_template('student_trial_view.html', tname=tname, sname=sname, fromtime=fromtime, date=date, link=link)
    return redirect('/')


@app.route('/tutor_full_detail_trial_class/<int:TrialClassId>', methods=['GET', 'POST'])
def tutor_full_detail_trial_class(TrialClassId):
    conn, cur = connection()
    meeting_link = request.form['meeting_link']
    cur.execute("Update trialclasses set MeetingId='{}' where TrialClassId='{}'".format(meeting_link, TrialClassId))
    conn.commit()

    return jsonify({'res': 'done'})


@app.route('/tutor_trial_drive_link/<int:TrialClassId>', methods=['GET', 'POST'])
def tutor_trial_drive_link(TrialClassId):
    if 'id' in session:
        if session['role'] == 'tutor':
            if request.method == 'POST':
                drive_link = request.form['drive_link']
                conn, cur = connection()
                cur.execute("UPDATE `trialclasses` SET VideoLink='{}' WHERE TrialClassId='{}'".format(drive_link, TrialClassId))
                conn.commit()
                return redirect('tutor_trial_classes')
    return redirect('/')


@app.route('/tutor_trial_detail/<id>', methods=['GET', 'POST'])
def tutor_trial_detail(id):
    if 'id' in session:
        if session['role'] == 'tutor':
            conn, cur = connection()
            cur.execute("Select * from trialClasses where TrialClassId='{}'".format(id))
            res = cur.fetchall()
            cur.execute("Select Name from studentlogin where StudentId='{}'".format(res[0][1]))
            tn = cur.fetchall()
            cur.execute("Select SkillName from skills where SkillId='{}'".format(res[0][3]))
            sn = cur.fetchall()
            cur.execute("Select FromTime from tutorslots where SlotId='{}'".format(res[0][6]))
            ft = cur.fetchall()
            trialid = res[0][0]
            tname = tn[0][0]
            sname = sn[0][0]
            fromtime = ft[0][0]
            date = res[0][5]
            link = res[0][9]
            return render_template('tutor_trial_detail.html', tname=tname, sname=sname,
                           fromtime=fromtime, date=date, link=link, trialid=trialid)
    return redirect('/')

@log.log_error()
@app.route('/tutor_trial_classes', methods=['GET', 'POST'])
def tutor_trial_classes():
    if 'id' in session:
        if session['role'] == 'tutor':
            TutorId = session['id']
            conn, cur = connection()
            cur.execute("Select * from trialClasses where TutorId='{}'".format(TutorId))
            res = cur.fetchall()
            fdata = []
            for row in res:
                row = list(row)
                row[5] = str(row[5])
                cur.execute("Select Name from studentlogin where StudentId='{}'".format(row[1]))
                name = cur.fetchall()
                row.append(name[0][0])
                cur.execute("Select SkillName from skills where SkillId='{}'".format(row[3]))
                name = cur.fetchall()
                row.append(name[0][0])
                cur.execute("Select FromTime from tutorslots where SlotId='{}'".format(row[6]))
                name = cur.fetchall()
                row.append(str(name[0][0]))
                fdata.append(row)
            flen = len(fdata)

            return render_template('tutor_trial_classes.html', fdata=fdata, flen=flen)
    return redirect('/')

@log.log_error()
@app.route('/trial_classes', methods=['GET', 'POST'])
def trial_classes():
    if 'id' in session:
        if session['role'] == 'student':
            StudentId = session['id']
            conn, cur = connection()
            cur.execute("Select * from trialClasses where StudentId='{}'".format(StudentId))
            res = cur.fetchall()
            fdata = []
            for row in res:
                row = list(row)
                row[5] = str(row[5])
                cur.execute("Select Name from tutordetails where TutorId='{}'".format(row[2]))
                name = cur.fetchall()
                row.append(name[0][0])
                cur.execute("Select SkillName from skills where SkillId='{}'".format(row[3]))
                name = cur.fetchall()
                row.append(name[0][0])
                cur.execute("Select FromTime from tutorslots where SlotId='{}'".format(row[6]))
                name = cur.fetchall()
                row.append(str(name[0][0]))
                fdata.append(row)
            flen = len(fdata)

            return render_template('student_trial_classes.html', flen=flen, fdata=fdata)
    return redirect('/')

@log.log_error()
@app.route("/student_trial_classes", methods=['GET', 'POST'])
def student_trial_classes():
    StudentId = session['id']
    conn, cur = connection()
    cur.execute(
        "SELECT src.TrialClassId,t.Name,ts.StartDate,tss.FromTime,tss.ToTime,s.SkillName,src.StudentId FROM `trialclasses` src LEFT JOIN `tutordetails` t on t.TutorId=src.TutorId LEFT JOIN `tutorschedule` ts on ts.TrialClassId=src.TrialClassId LEFT JOIN `scheduledetails` sd on sd.ScheduleId=ts.ScheduleId LEFT JOIN `tutorslots` tss on tss.SlotId=src.SlotId LEFT JOIN `days` d on d.DayId=tss.DayId LEFT JOIN `skills` s on s.SkillId=src.SkillId WHERE src.StudentId='{}'".format(
            StudentId))
    student_trial_data = cur.fetchall()
    return render_template('tutor-scheduled-detail.html', student_trial_data=student_trial_data)


# Student Can Show Trial Class View and Join Meeting
@log.log_error()
@app.route("/student_trialclass_view/<int:TrialClassId>", methods=['GET', 'POST'])
def student_trialclass_view(TrialClassId):
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()
            cur.execute(
                "SELECT src.TrialClassId,t.Name,ts.StartDate,tss.FromTime,tss.ToTime,s.SkillName,d.DayName,src.MeetingId FROM `studentrequesttrialclasses` src LEFT JOIN `tutordetails` t on t.TutorId=src.TutorId LEFT JOIN `tutorschedule` ts on ts.TrialClassId=src.TrialClassId LEFT JOIN `scheduledetails` sd on sd.ScheduleId=ts.ScheduleId LEFT JOIN `tutorslots` tss on tss.SlotId=src.SlotId LEFT JOIN `days` d on d.DayId=tss.DayId LEFT JOIN `skills` s on s.SkillId=src.SkillId WHERE src.TrialClassId='{}'".format(
                    TrialClassId))
            student_myclasses_view_data = cur.fetchone()
            return render_template('student-trialclass-view.html', student_myclasses_view_data=student_myclasses_view_data)
    return redirect('/')

@log.log_error()
@app.route('/getTimeZone', methods=['GET', 'POST'])
def getTimeZone():
    session['tz_offset'] = request.form['zone']
    session['current_date'] = request.form['today']

    return jsonify({'res':'done'})

@log.log_error()
@app.route('/schedule_form', methods=['GET', 'POST'])
def schedule_form():
    if 'id' in session:
        if session['role'] == 'student':
            id = session['tid']
            fl, fc, fs, dates, dateshown = getSlots(id)
            length = len(fl)

            return render_template('schedule_form.html', fl=fl, fc=fc, dates=dates, fs=fs, length=length)
    return redirect('/')

@log.log_error()
@app.route('/payment_form', methods=['GET', 'POST'])
def payment_form():
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()
            cur.execute("Select Name from tutordetails where TutorId='{}'".format(session['tid']))
            name = cur.fetchall()
            tname = name[0][0]
            cur.execute("Select SkillName from skills where SKillId='{}'".format(session['skillid']))
            skill = cur.fetchall()
            sname = skill[0][0]
            return render_template('payment_form.html', tname=tname, sname=sname)
    return redirect('/')

@log.log_error()
@app.route('/setTutorInfo', methods=['GET', 'POST'])
def setTutorInfo():
    session['tid'] = request.form['tid']
    session['tcost'] = request.form['cost']
    session['skillid'] = request.form['skillid']
    return jsonify({'res':'done'})

@log.log_error()
@app.route('/setTutorSlot', methods=['GET', 'POST'])
def setTutorSlot():
    data = request.form['slotid']
    data = data.split('_')
    session['slotid'] = data[0]
    session['trialdate'] = data[1]
    session['stime'] = data[2]

    return jsonify({'res':'done'})

@log.log_error()
@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist():
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()
            cur.execute("Select TutorId, SkillId from studentwishlist where StudentId='{}'".format(session['id']))
            res = cur.fetchall()
            data = []
            for i in range(len(res)):
                data1= []
                cur.execute("Select Name, Headline, Description, Image from tutordetails where TutorId='{}'".format(res[i][0]))
                tutor=cur.fetchall()
                data1.append(tutor[0][0])
                data1.append(tutor[0][1])
                data1.append(tutor[0][2])
                data1.append(tutor[0][3])

                cur.execute("Select CostPerHour from tutorskills where TutorId='{}' and SKillId='{}'".format(res[i][0], res[i][1]))
                cost=cur.fetchall()
                data1.append(cost[0][0])

                cur.execute("Select SkillName from skills where SKillId='{}'".format(res[i][1]))
                sname=cur.fetchall()
                data1.append(sname[0][0])

                data.append(data1)

            datalen = len(data)
            print(datalen,"datetime")
            return render_template('wishing_list_page.html', datalen=datalen, data=data)

    return redirect('/')

@log.log_error()
@app.route('/cart_data', methods = ['GET', 'POST'])
def cart_data():
        if request.method=='POST':
            StudentId = session['id']
            data=request.form['id']
            conn, cur = connection()
            data=data.split('_')
            print(data,"data1487")
            cur.execute("select * from studentwishlist where StudentId='{}' and TutorId='{}' and SKillId='{}'".format(StudentId, data[0], data[1]))
            fetchDetails = cur.fetchone()
            if fetchDetails:
                cur.execute("delete from studentwishlist where StudentId='{}' and TutorId='{}' and SKillId='{}'".format(StudentId, data[0], data[1]))
                conn.commit()
                print("delete div")
                return jsonify({'res':'delete'})
                
            else:
                cur.execute("Insert into studentwishlist(StudentId, TutorId, SKillId) values('{}','{}','{}')".format(StudentId, data[0], data[1]))
                conn.commit()
                print("done div")
                return jsonify({'res':'done'})

@log.log_error()
@app.route('/myclasses', methods = ['GET', 'POST'])
def myclasses():

    return render_template('myclasses.html')

@app.route("/trialpaymentdemo", methods=['GET', 'POST'])
def trialpaymentdemo():
    conn, cur = connection()
    tid = session['tid']
    cost = session['tcost']
    date = session['trialdate']
    slotid = session['slotid']
    skillid = session['skillid']
    cur.execute(
        "Insert into trialclasses(StudentId, TutorId, SkillId, Date, SlotId, PaymentRequestId) values('{}', '{}', '{}', '{}', '{}', '')".format(
            session['id'], tid, skillid, date, slotid
        ))
    conn.commit()
    subject = 'Trial Class Booked Successfully!!'
    to = session['email']
    body1 = 'Congratulations ' + ','
    body2 = 'Your trial class has been booked successfully!! '
    body = "{}\n{}\n".format(body1, body2)
    send_email(subject, to, body)

    cur.execute("Select Email from tutorlogin where TutorId='{}'".format(tid))
    tmail = cur.fetchall()

    # subject = 'Trial Class Booked'
    # to = tmail[0][0]
    # body1 = 'Congratulations ' + ','
    # body2 = 'A student has booked your trial class!!'
    # body = "{}\n{}\n".format(body1, body2)
    # send_email(subject, to, body)
    flash("Your trial class is booked successfully!!")
    flash("Success")
    flash("success")
    return redirect(url_for('trial_classes'))

@app.route("/admin_student_creation", methods=['GET', 'POST'])
def admin_student_creation():
    if 'id' in session:
        if session['role']=='admin':
            if request.method == 'GET':
                return render_template('admin_student_creation.html')
            if request.method == 'POST':
                conn, cur = connection()
                sname = request.form['sname']
                smail = request.form['smail']
                tname = request.form['tname']
                tmail = request.form['tmail']
                classdate = request.form['classdate']
                amount = request.form['amount']
                cur.execute("Insert into adminClass(StudentName, StudentEmail, TutorName, TutorEmail, ClassDate, Amount) Values('{}','{}','{}','{}','{}','{}')".format(
                    sname, smail, tname, tmail, classdate, amount
                ))
                conn.commit()
                flash('Data Submitted Successfully!!')
                flash("Success")
                flash("success")
                return render_template('admin_student_creation.html')
    return redirect('/')

@app.route("/admin_show_classes", methods=['GET', 'POST'])
def admin_show_classes():
    if 'id' in session:
        if session['role']=='admin':
            if request.method == 'GET':
                conn, cur = connection()
                cur.execute("Select Id, StudentName, StudentEmail, TutorName, TutorEmail, ClassDate, Amount, Schedule, PaymentDate, PaymentStatus from adminClass")
                classdata = cur.fetchall()
                print(classdata)

                return render_template('admin_show_classes.html', classdata=classdata)
    return redirect('/')

@app.route("/uploadschedule", methods=['GET', 'POST'])
def uploadschedule():
    topic = request.form.getlist('topic[]')
    date = request.form.getlist('date[]')
    time = request.form.getlist('time[]')
    id = request.form['id']
    print(topic, date, time, id)

    conn, cur=connection()
    for i in range(len(topic)):
        cur.execute("Insert into adminSchedule(ClassId, Topic, Date, Time) Values('{}','{}','{}','{}')".format(
            id, topic[i], date[i], time[i]
        ))
        conn.commit()
        cur.execute("update adminClass set Schedule='y' where Id='{}'".format(id))
        conn.commit()

    return jsonify({'res':'done'})

@app.route("/getschedule", methods=['GET', 'POST'])
def getschedule():
    print(request.form)
    id = request.form['id']
    conn, cur = connection()
    cur.execute("Select Id, Topic, Date, Time from adminSchedule where ClassId='{}'".format(id))
    res = cur.fetchall()
    sid = []
    topic = []
    date = []
    time = []
    for i in range(len(res)):
        sid.append(res[i][0])
        topic.append(res[i][1])
        date.append(res[i][2])
        time.append(str(res[i][3]))

    return jsonify({'sid':sid, 'topic':topic, 'date' : date, 'time' : time})

@app.route("/admin_show_transactions", methods=['GET', 'POST'])
def admin_show_transactions():
    if 'id' in session:
        if session['role']=='admin':
            conn, cur = connection()
            cur.execute(
                "Select Id, StudentName, StudentEmail, TutorName, TutorEmail, ClassDate, Amount, Schedule, PaymentDate, PaymentStatus from adminClass")
            classdata = cur.fetchall()
            print(classdata)

            return render_template('admin_show_transactions.html', classdata=classdata)
    return redirect('/')

@app.route("/changepaymentinfo", methods=['GET', 'POST'])
def changepaymentinfo():
    mid = request.form['mid']
    pdate = request.form['pdate']
    pstatus = request.form['pstatus']
    conn, cur = connection()
    cur.execute("Update adminClass set PaymentDate='{}' , PaymentStatus='{}' where Id='{}'".format(pdate, pstatus, mid))
    conn.commit()
    return jsonify({'res':'done'})



@app.route('/make_schedule', methods=['GET', 'POST'])
def make_schedule():
    if 'id' in session:
        if session['role'] == 'tutor':
            if request.method == 'GET':
                conn, cur = connection()
                cur.execute("Select * from days")
                days = cur.fetchall()
                return render_template('make_schedule.html', days=days)

            if request.method == 'POST':
                dayid = request.form['day']
                slottime = request.form['slottime']
                startdate = request.form['startDate']
                no_of_classes = request.form['noOfClasses']
                print(request.form.getlist('topic'))
                topiclist = request.form.getlist('topic')
                print(topiclist)
                # topiclist = scheduledata.split(',')
                print(topiclist)
                trial_class_id = 1
                # trial_class_id=request.form['trialclassid']
                conn, cur = connection()
                cur.execute("SELECT SlotId FROM tutorslots WHERE dayid='{}' and FromTime='{}' and TutorId='{}'".format(
                    dayid, slottime, session['id']))
                result = cur.fetchone()
                if result is None:
                    fromtime = datetime.datetime.strptime(slottime, '%H:%M')
                    fromtime += datetime.timedelta(hours=1)
                    totime = str(fromtime).split(' ')
                    cur.execute(
                        "Insert INTO tutorslots(TutorId,DayId,FromTime,ToTime) Values('{}','{}','{}','{}')".format(
                            session['id'], dayid, slottime, totime[1]))
                conn.commit()
                conn, cur = connection()
                cur.execute("SELECT SlotId FROM tutorslots WHERE dayid='{}' and FromTime='{}' and TutorId='{}'".format(
                    dayid, slottime, session['id']))
                slotid = cur.fetchone()
                cur.execute(
                    "Insert INTO tutorschedule(TrialClassId,NoOfClasses,StartDate,SlotId) Values('{}','{}','{}','{}')".format(
                        trial_class_id, no_of_classes, startdate, slotid[0]))
                conn.commit()
                print("Insert INTO tutorschedule(TrialClassId,NoOfClasses,StartDate) Values('{}','{}','{}')".format(
                    trial_class_id, no_of_classes, startdate))
                conn, cur = connection()
                cur.execute("SELECT ScheduleId from tutorschedule WHERE TrialClassId='{}'".format(
                    trial_class_id))
                print("SELECT ScheduleId from tutorschedule WHERE TrialClassId='{}'".format(
                    trial_class_id))
                ScheduleId = cur.fetchone()
                print(ScheduleId)

                conn, cur = connection()

                for i in range(int(no_of_classes)):
                    cur.execute("SET foreign_key_checks = 0")
                    cur.execute("INSERT INTO scheduledetails(ScheduleId,Topic) VALUES('{}','{}')".format(
                        ScheduleId[0], topiclist[i]))
                conn.commit()

                return redirect(url_for('make_schedule'))

            return redirect(url_for('make_schedule'))
    return redirect('/')

#
# @app.route('/checkslotavailability', methods=['GET', 'POST'])
# def checkslotavailability():
#     conn, cur = connection()
#     dayid = request.form['did']
#     slottime = request.form['slottime']
#     startdate = request.form['startDate']
#
#     cur.execute("SELECT SlotId from tutorslots where TutorId='{}' and DayId='{}' and FromTime='{}'".format(
#         session['id'], dayid, slottime))
#     result = cur.fetchall()
#     if result:
#         cur.execute("SELECT * from trialclasses where TutorId='{}' and slotId='{}' and Date='{}'".format(
#             session['id'], result[0][0], startdate))
#         result1 = cur.fetchall()
#         if result1 is None:
#             cur.execute("SELECT * from myclassesslots where slotId='{}' and Date='{}'".format(
#                 result[0][0], startdate))
#             result2 = cur.fetchall()
#             if result2:
#                 return jsonify({'res': 'exists'})
#             else:
#                 return jsonify({'res': 'empty'})
#         else:
#             return jsonify({'res': 'exists'})
#     else:
#         return jsonify({'res': 'empty'})


@app.route('/group_class_creation', methods=['GET', 'POST'])
def group_class_creation():
    if request.method == 'POST':
        title = request.form['title']
        title    = title.replace("'", "''")
        desc = request.form['desc']
        desc    = desc.replace("'", "''")
        image = request.files['image']
        subcategoryid = request.form['subcategory']
        learn = request.form.getlist('learn[]')
        startdate = request.form.getlist('startdate[]')
        noofclasses = request.form.getlist('nclasses[]')
        dayid = request.form.getlist('dayid[]')
        fromtime = request.form.getlist('fromtime[]')
        totime = request.form.getlist('totime[]')
        count_div_row = request.form.getlist('count_div_row[]')
        session['id'] = 1
        #fromtime = list(fromtime)
        print(startdate,"startdate",noofclasses,"noofclasses",dayid,"",fromtime,"fromtime",totime,"totime",count_div_row,"count_div_row")
        conn, cur = connection()
        cur.execute("Insert into groupClass(TutorId, Title, Description, SubCategoryId) values('{}','{}','{}','{}')".format(
            session['id'], title, desc, subcategoryid
        ))
        conn.commit()
        cur.execute("Select LAST_INSERT_ID() from groupClass")
        classid = cur.fetchall()
        filename = secure_filename(image.filename)
        ext = filename.split('.')
        name = str(classid[0][0]) + '.' + ext[len(ext) - 1]
        image.save(os.path.join(os.getcwd() + '\\static\\groupclass', name))
        cur.execute("Update groupClass set Image = '{}' where GroupClassId='{}'".format(name, classid[0][0]))
        conn.commit()
        for i in learn:
            cur.execute("Insert into groupClassLearn(GroupClassId, Name) values('{}','{}')".format(
                classid[0][0], i
            ))
            conn.commit()
        # convert fromtime , totime and days in new list
        st=[]
        ttime=[]
        dt=[]
        for s in count_div_row:
            from_time_list =[]
            totime_list    =[]
            days_list      =[]
            #print(s,"dfsdfsdffsd")
            for m in range(0,int(s)):
                # print(m,"mmmmmmmm")
                # print(fromtime[0],"fromtime[0]",m)
                from_time_list.append(fromtime[0])
                totime_list.append(totime[0])
                days_list.append(dayid[0])
                fromtime.pop(0)
                totime.pop(0)
                dayid.pop(0)
            st.append(from_time_list)
            ttime.append(totime_list)
            dt.append(days_list)

        print('starttime final list :', st)
        print('totime final list :', ttime)
        print('days final list :', dt)

        for i in range(len(startdate)):
            print('i: ', i)
            sd = startdate[i]
            nc = noofclasses[i]
            did = dt[i]
            ft = st[i]
            tt = ttime[i]
            sdate = datetime.datetime.strptime(sd, '%Y-%m-%d')
            sdid = sdate.weekday()
            if sdid == 6:
                sdid = 0
            else:
                sdid = sdid + 1
            print('did: ', did)
            dates = []
            dayorder = []
            ftorder = []
            ttorder = []
            dayidlist = list(did)
            print('dayidlist:', dayidlist)
            #print(sdid,"sdid",type(did))
            sdid = str(sdid)
            if sdid in did:
                dayorder.append(sdid)
                dates.append(sdate)
                did.remove(sdid)
            print('dayidlist1:', dayidlist)
            #print(type(did),"sdidlist 2068")
            did = list(did)
            #print(sdid,"sdid",did,"2070")
            did.sort(reverse=True)
            # did  = str(did)
            # sdid  = str(sdid)
            #print(type(sdid),"sdid",type(did),"did")
            value = nearest_largest_value(sdid, did)

            if value!=None:
                dayorder.append(value)
                ind = did.index(value)
                while len(did)-1>ind:
                    dayorder.append(did[ind+1])
                    did.remove(did[ind+1])
            print('dayidlist3:', dayidlist)
            did.sort()
            for i in did:
                dayorder.append(i)
            count = 0
            curdate = sdate
            # print(nc,"ncccccccccccccccc")
            # print(dayorder,"dayorder",dayidlist,"dayidlist",ft,"ft")
            print(dayidlist, dayorder, count, 'dataprev')
            for num in range(int(nc)):
                if num == 0:
                    if dates and len(dayorder)>1:
                        print(dayidlist, dayorder, count, 'data')
                        ind = dayidlist.index(str(dayorder[count]))
                        ftorder.append(ft[ind])
                        ttorder.append(tt[ind])
                        count = count + 1
                if int(dayorder[count]) == 0:
                    day = 6
                else:
                    day = int(dayorder[count])- 1
                curdate = next_weekday(curdate, day)
                ind = dayidlist.index(str(dayorder[count]))
                ftorder.append(ft[ind])
                ttorder.append(tt[ind])
                dates.append(curdate)
                #print(dates,"2114***********************")
                if len(dayorder)-1 > count:
                    count = count + 1
                else:
                    count = 0
            # print(dates[0],"StartDate")
            # print(dates[len(dates)-1],"EndDate")
            cur.execute("Insert into groupClassBatch(GroupClassId, StartDate, EndDate, NoOfClasses) values('{}','{}','{}','{}')".format(
                classid[0][0], dates[0], dates[len(dates)-1], nc
            ))
            conn.commit()
            cur.execute("Select LAST_INSERT_ID() from groupClassBatch")
            batchid = cur.fetchall()
            #print(len(dates),"dates")
            print(batchid, dates, ftorder, ttorder, 'data')
            for count in range(len(ftorder)):
                # print(ftorder[count],"FromTime")
                # print(ttorder[count],"ToTime")

                cur.execute("Insert into groupClassBatchSchedule(BatchId, Date, FromTime, ToTime) values('{}','{}','{}','{}')".format(
                    batchid[0][0], dates[count], ftorder[count], ttorder[count]
                ))
                conn.commit()
         #fetch subcategory
        cur.execute("Select * from groupclasscategories")
        Category_data = cur.fetchall()
        Category_len = len(Category_data)
        #fetch days
        cur.execute("Select * from days")
        days_data = cur.fetchall()
        days_data_len = len(days_data)
        #return render_template('group_class_creation.html')
        return render_template('group_class_creation.html',days_data=days_data,days_data_len=days_data_len,Category_data=Category_data,Category_len=Category_len)
    else:
        #fetch subcategory
        conn, cur = connection()
        cur.execute("Select * from groupclasscategories")
        Category_data = cur.fetchall()
        Category_len = len(Category_data)
        #fetch days
        cur.execute("Select * from days")
        days_data = cur.fetchall()
        days_data_len = len(days_data)
        return render_template('group_class_creation.html',days_data=days_data,days_data_len=days_data_len,Category_data=Category_data,Category_len=Category_len)



        

#fetchsubCategory
@app.route('/fetchsubCategory', methods=['GET', 'POST'])
def fetchsubCategory():
    if request.method=="POST":
        conn, cur = connection()
        category_id  = request.form['category_id']
        cur.execute(
            "SELECT *  FROM groupclasssubcategories where CategoryId='{}'".format(
                category_id))
        subcategory_data = cur.fetchall()
        return jsonify({'res': subcategory_data})

@app.route('/group_class_homepage', methods=['GET', 'POST'])
def group_class_homepage():
    return render_template('group_class_homepage.html')



#added by rishabh 6-6-2021
@app.route('/group_listing', methods=['GET', 'POST'])

@app.route('/group_listing', methods=['GET', 'POST'])
def group_listing():
    conn, cur =connection()
    cur.execute("Select * from groupClass")
    groupclass = cur.fetchall()
    gcdata = []
    # GroupClassId, TutorId, Title, Description, Image, SubCategoryId
    for row in groupclass:
        row = list(row)
        #print(row[0],"row[0]")
        cur.execute("Select BatchId, StartDate, EndDate, NoOfClasses, NoOfStudents from groupClassBatch where GroupClassId='{}'".format(
            row[0]
        ))
        batches = cur.fetchall()
        for batch in batches:
            batch = list(batch)
            row = row + batch
        gcdata.append(row)
    gcdata_len = len(gcdata)
    # fetch batch timing
    cur.execute("""select g.GroupClassId,monthname(gb.StartDate), day(gb.StartDate), year(gb.StartDate),dayname(gb.StartDate),TIME_FORMAT(gc.FromTime, "%h:%i %p")  from groupclass g
    inner join groupclassbatch gb on g.GroupClassId = gb.GroupClassId
    left join groupclassbatchschedule gc on gc.BatchId = gb.BatchId
    group by (g.GroupClassId)""")
    grouptiming = cur.fetchall()
    count_batch_list   = []
    for g in range(0, len(grouptiming)):
        grouptiming = list(grouptiming)
        grouptiming_len = len(grouptiming)
        #count total batch class
        cur.execute("""select count(g.GroupClassId) from groupclass g
        inner join groupclassbatch gb on g.GroupClassId = gb.GroupClassId
        where g.GroupClassId ='{}'""".format(
            grouptiming[g][0]
        ))
        count_batch_timing = cur.fetchall()
        for b in range(0,len(count_batch_timing)):
            count_batch_list.append(count_batch_timing[b][0]-1)
    return render_template('group_listing.html',gcdata=gcdata,gcdata_len=gcdata_len,grouptiming=grouptiming,grouptiming_len=grouptiming_len,count_batch_list=count_batch_list)




#added by rishabh 6-6-2021

@app.route('/group_detailing/<id>', methods=['GET', 'POST'])
def group_detailing(id):
    conn, cur = connection()
    #fetch tutor_details
    cur.execute("""select g.GroupClassId,t.Name, c.CountryName, t.Languages,t.Description,g.Title , g.Description,t.Image  from groupClass g
    join tutordetails t on t.TutorId= g.TutorId
    inner join country c on c.CountryId= t.Country where g.GroupClassId='{}'""".format(
         id
    ))
    tutur_details = cur.fetchall()
    tutor_len     = len(tutur_details)
    #print(tutor_len,"id")
    #fetch what will learn in classes
    cur.execute("Select * from groupclasslearn where GroupClassId='{}'".format(
        id
    ))
    learning_details = cur.fetchall()
    learning_len     = len(learning_details)
    #fetch batch timing
    cur.execute("""select g.BatchId,g.GroupClassId from groupClassBatch g 
     where g.GroupClassId='{}'  """.format(
        id
    ))
    batch_learning         = cur.fetchall()
    batch_learning_len     = len(batch_learning)
    batch_counter_list   = []
    count_batch_counter  = []
    month_name_list      = []
    day_name_list        = []
    day_list             = []
    day_name_enddate     = []
    day_enddate          = []
    year_list            = []
    month_name_end_date  = []
    from_time_list       = []
    to_time_list         = []
    # fetch all class of batch
    for bid in range(0,batch_learning_len):
        cur.execute("""select g.BatchId,g.GroupClassId,monthname(s.Date),
        dayname(s.Date), day(s.Date),s.FromTime, 
        s.ToTime, year(s.Date) from groupClassBatch g
        left join groupClassBatchSchedule s on s.BatchId = g.BatchId
         where g.GroupClassId='{}' and g.BatchId= '{}' """.format(
            batch_learning[bid][1],batch_learning[bid][0]
        ))
        batch_counter_list.append(batch_learning[bid][0])
        batch_class_details        = cur.fetchall()
        #print(len(batch_class_details),"len(batch_class_details)",batch_class_details)
        i = 0
        for d in range(0, len(batch_class_details)):
            i=i+1
            #batch_class_counter_list.append(batch_class_details[d][2])
            month_name_list.append(batch_class_details[d][2])
            day_name_list.append(batch_class_details[d][3])
            day_list.append(batch_class_details[d][4])
            from_time_list.append(batch_class_details[d][5])
            to_time_list.append(batch_class_details[d][6])
            year_list.append(batch_class_details[d][7])
        count_batch_counter.append(i)
    # fetch all recommended course
    cur.execute("""select g.GroupClassId ,g.Title,g.Image,monthname(gb.StartDate),day(gb.StartDate),year(gb.StartDate),gb.NoOfClasses,count(*) from  groupclass g 
                inner join groupClassBatch gb on gb.GroupClassId = g.GroupClassId
                where gb.GroupClassId not in ('{}')
                group by gb.GroupClassId
                """.format(
        id
    ))
    recommended_class = cur.fetchall()
    recommended_class_len = len(recommended_class)
    #print(month_name_list,"batch_class_counter_list")
    #count total batch
    cur.execute("select count(*) from  groupClassBatch where GroupClassId = '{}'".format(
        id
    ))
    count_total_batch     = cur.fetchone()
    count_total_batch     = count_total_batch[0]
    #fetch min batchid to count total class in first batch
    cur.execute("select min(BatchId) from  groupClassBatch where GroupClassId = '{}'".format(
        id
    ))
    min_batch_id          = cur.fetchone()
    min_batch_id          = min_batch_id[0]
    #count total class in first batch
    cur.execute("""select count(g.BatchId)  from groupClassBatch g
        left join groupClassBatchSchedule s on s.BatchId = g.BatchId
        where g.BatchId='{}'
        group by g.BatchId""".format(
        min_batch_id
    ))
    total_class_first_batch  = cur.fetchone()
    total_class_first_batch  = total_class_first_batch[0]
    return render_template('group_detailing.html',total_class_first_batch=total_class_first_batch,count_total_batch=count_total_batch,year_list=year_list,to_time_list=to_time_list,from_time_list=from_time_list,day_enddate=day_enddate,day_name_enddate=day_name_enddate,month_name_end_date=month_name_end_date,day_name_list=day_name_list,day_list=day_list,month_name_list=month_name_list,count_batch_counter=count_batch_counter,recommended_class=recommended_class,recommended_class_len=recommended_class_len,batch_learning=batch_learning,batch_learning_len=batch_learning_len,tutor_len=tutor_len,tutur_details=tutur_details,learning_len=learning_len,learning_details=learning_details)







def nearest_largest_value(n, values):
    return min([v for v in values if v >= n] or [None])

def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)

# @app.route('/group_class_creation', methods=['GET', 'POST'])
# def group_class_creation():
#     title = request.form['title']
#     desc = request.form['desc']
#     image = request.files['image']
#     subcategoryid = request.form['subcategory']
#     learn = request.form.getlist('learn[]')
#     startdate = request.form.getlist('startdate[]')
#     noofclasses = request.form.getlist('nclasses[]')
#     dayid = request.form.getlist('dayid[]')
#     fromtime = request.form.getlist('fromtime[]')
#     totime = request.form.getlist('totime[]')
#
#     conn, cur = connection()
#     cur.execute("Insert into groupClass(TutorId, Title, Description, SubCategoryId) values('{}','{}','{}','{}')".format(
#         session['id'], title, desc, subcategoryid
#     ))
#     conn.commit()
#
#     cur.execute("Select LAST_INSERT_ID() from groupClass")
#     classid = cur.fetchall()
#
#     filename = secure_filename(image.filename)
#     ext = filename.split('.')
#     name = str(classid[0][0]) + '.' + ext[len(ext) - 1]
#     image.save(os.path.join(os.getcwd() + '/static/groupclass', name))
#
#     cur.execute("Update groupClass set Image = '{}' where GroupClassId='{}'".format(name, classid[0][0]))
#     conn.commit()
#
#     for i in learn:
#         cur.execute("Insert into groupClassLearn(GroupClassId, Name) values('{}','{}')".format(
#             classid[0][0], i
#         ))
#         conn.commit()
#
#     for i in range(len(startdate)):
#         sd = startdate[i]
#         nc = noofclasses[i]
#         did = dayid[i]
#         ft = fromtime[i]
#         tt = totime[i]
#         sdate = datetime.datetime.strptime(sd, '%Y-%m-%d')
#         sdid = sdate.weekday()
#         if sdid == 6:
#             sdid = 0
#         else:
#             sdid = sdid + 1
#
#         dates = []
#         dayorder = []
#         ftorder = []
#         ttorder = []
#         dayidlist = did
#         if sdid in did:
#             dayorder.append(sdid)
#             dates.append(sdate)
#             did.remove(sdid)
#
#         sdid = sdid.sort(reverse=True)
#
#         value = nearest_largest_value(sdid, did)
#         if value!=None:
#             dayorder.append(value)
#             ind = did.index(value)
#             while len(did)-1>ind:
#                 dayorder.append(did[ind+1])
#                 did.remove(did[ind+1])
#
#         sdid = sdid.sort()
#
#         for i in sdid:
#             dayorder.append(i)
#
#         count = 0
#         curdate = sdate
#         for num in range(nc):
#             if num == 0:
#                 if dates and len(dayorder)>1:
#                     ind = dayidlist.index(dayorder[count])
#                     ftorder.append(ft[ind])
#                     ttorder.append(tt[ind])
#                     count = count + 1
#             if dayorder[count] == 0:
#                 day = 6
#             else:
#                 day = dayorder[count]- 1
#             curdate = next_weekday(curdate, day)
#             ind = dayidlist.index(dayorder[count])
#             ftorder.append(ft[ind])
#             ttorder.append(tt[ind])
#             dates.append(curdate)
#
#             if len(dayorder)-1 > count:
#                 count = count + 1
#             else:
#                 count = 0
#
#         cur.execute("Insert into groupClassBatch(GroupClassId, StartDate, EndDate, NoOfClasses) values('{}','{}','{}','{}')".format(
#             classid[0][0], dates[0], dates[len(dates)-1], nc
#         ))
#         conn.commit()
#
#         cur.execute("Select LAST_INSERT_ID() from groupClassBatch")
#         batchid = cur.fetchall()
#
#         for count in range(len(dates)):
#             cur.execute("Insert into groupClassBatchSchedule(BatchId, Date, FromTime, ToTime) values('{}','{}','{}','{}')".format(
#                 batchid[0][0], dates[count], ftorder[count], ttorder[count]
#             ))
#             conn.commit()
#
#     return render_template('group_class_creation.html')

@app.route("/hr_tutor_registration", methods=['GET', 'POST'])
def hr_tutor_registration():
    if 'id' in session:
        if session['role'] == 'hr':
            if request.method == 'GET':
                return render_template('hr_tutor_registration.html')
            if request.method == 'POST':
                conn, cur = connection()
                print(request.form)
                print(request.files)

                tname = request.form['tname']
                tmail = request.form['tmail']
                contact = request.form['contact']
                profilelink = request.form['profilelink']
                skill = request.form.getlist('skill')
                resume = request.files['resume']

                cur.execute("Insert into tutorsInfo(Name, Email, Contact, ProfileLink) values('{}','{}','{}','{}')".format(
                    tname, tmail, contact, profilelink
                ))
                conn.commit()

                cur.execute("Select LAST_INSERT_ID() from tutorsInfo")
                tutorid = cur.fetchall()

                for name in skill:
                    cur.execute("Insert into tutorsInfoSkills(TutorId, Name) values('{}','{}')".format(
                        tutorid[0][0], name
                    ))
                    conn.commit()

                filename = secure_filename(resume.filename)
                ext = filename.split('.')
                name = str(tutorid[0][0]) + '.' + ext[len(ext) - 1]
                resume.save(os.path.join(os.getcwd() + '\\static\\hrtutors', name))
                cur.execute("Update tutorsInfo set Resume='{}' where TutorId='{}'".format(name, tutorid[0][0]))
                conn.commit()

                return render_template('hr_tutor_registration.html')

    return redirect('/')

@app.route("/hr_tutor_search", methods=['GET', 'POST'])
def hr_tutor_search():
    if 'id' in session:
        if session['role'] == 'hr':
            if request.method == 'GET':
                return render_template('hr_tutor_search.html', fdata = [], skill = '')
            if request.method == 'POST':
                conn, cur = connection()
                skill = request.form['skill']
                cur.execute("Select distinct(TutorId) from tutorsInfoSkills where Name='{}'".format(skill))
                tid = cur.fetchall()
                fdata = []
                for i in range(len(tid)):
                    cur.execute("Select Name, Email, Contact, ProfileLink, Resume from tutorsInfo where TutorId='{}'".format(tid[i][0]))
                    data = cur.fetchone()
                    fdata.append(list(data))
                print(fdata)
                return render_template('hr_tutor_search.html', fdata = fdata, skill = skill)

    return redirect('/')

@app.route("/student_my_class", methods=['GET', 'POST'])
def student_my_class():
    return render_template('student-my-class.html')

@app.route("/tutor_my_class", methods=['GET', 'POST'])
def tutor_my_class():
    return render_template('tutor-my-class.html')

@app.route("/create_group_class", methods=['GET', 'POST'])
def create_group_class():
    return render_template('create_group_class.html')


# =====================================CREATE BLOG=========================================
@app.route('/create_blog',methods=["GET","POST"])
def create_blog():
    if 'id' in session:
        if session['role'] == 'admin':
           if request.method == 'GET':
               now = datetime.datetime.now()
               formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
               print(formatted_date,"get")
               return render_template('create-blog.html')
           if request.method == 'POST':
               imgname='blog'
               blog_title = request.form.get('blog_title')
               blog_title= blog_title.replace("'","").replace('"', '')
               blog_url = re.sub("\W+",' ', blog_title)
               blog_url=re.sub("[ ,.?]", "-", str(blog_url))
               if blog_url.endswith("-"):
                   blog_url = blog_url[:-1]
               blog_url= blog_url.replace("'","").replace('"', '')
               blogger_name    = request.form.get('blogger_name')
               blog_description = request.form.get('blog_description')
               blog_description= blog_description.replace("'","").replace('"', '')
               blog_image =     request.files.getlist('blog_image')
               uploads_dir = "static/assets/images/blog"
               os.makedirs(uploads_dir, exist_ok=True)
               conn, cur = connection()
               cur.execute("Select BLOG_ID  from blog order by BLOG_ID desc LIMIT 1")
               result=cur.fetchall()
               liveclassid=result[0][0]
               blog_url  = blog_url+str(liveclassid)
               now = datetime.datetime.now()
               formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
               if liveclassid=='':
                    imgname='1'
               else:
                    imgname=liveclassid
               for i in blog_image:
                   i.save(os.path.join(uploads_dir, str(imgname) + '.jpeg'))
                   img = str(imgname) + '.jpeg'
               cur.execute("Insert into blog(HEADING,DESCRIPTION,AUTHOR,DATE,BLOG_IMAGE,BLOG_URL)  VALUES ('{}', '{}', '{}', '{}','{}','{}')".format(blog_title,blog_description,blogger_name,formatted_date,img,blog_url))
               conn.commit()
               return redirect(url_for('create_blog'))
    return redirect('/')

@app.route('/update_blog', methods=["GET", "POST"])
def update_blog():
    if 'id' in session:
        if session['role'] == 'admin':
            if request.method == 'POST':
                imgname = 'blog'
                blog_title = request.form.get('blog_title')
                blog_title = blog_title.replace("'", "").replace('"', '')
                blog_url = re.sub("\W+", ' ', blog_title)
                blog_url = re.sub("[ ,.?]", "-", str(blog_url))
                if blog_url.endswith("-"):
                    blog_url = blog_url[:-1]
                blogger_name = request.form.get('blogger_name')
                blog_description = request.form.get('blog_description')
                blog_description = blog_description.replace("'", "").replace('"', '')
                conn, cur = connection()
                updateid = request.form.get('update_id')
                cur.execute("update blog set HEADING='{}',DESCRIPTION='{}',AUTHOR='{}',BLOG_URL='{}' where BLOG_ID='{}'".format(
                    blog_title, blog_description, blogger_name, blog_url, updateid))
                # print("Insert into blog(HEADING,DESCRIPTION,AUTHOR,DATE,BLOG_IMAGE)  VALUES ('{}', '{}', '{}', '{}','{}')".format(blog_title,blog_description,blogger_name,formatted_d)
                conn.commit()
                return redirect(url_for('blog_listing'))
    return redirect('/')

# ================================= Blog ============================================
@app.route('/blog',methods=["GET","POST"])
def all_blog():

    conn, cur = connection()
    cur.execute("Select BLOG_ID,HEADING,DESCRIPTION,AUTHOR,DATE,BLOG_IMAGE,MONTHNAME(DATE), year(DATE), day(DATE),BLOG_URL from blog order by BLOG_ID desc")
    result=cur.fetchall()
    blog_len=len(result)
    length=[]
    BLOG_ID=[]
    HEADING=[]
    DESCRIPTION=[]
    AUTHOR=[]
    BLOG_IMAGE=[]
    MONTHNAME=[]
    year=[]
    day=[]
    BLOG_URL=[]
    for i in range(len(result)):
        BLOG_ID.append(result[i][0])
        HEADING.append(result[i][1])
        DESCRIPTION.append(result[i][2])
        AUTHOR.append(result[i][3])
        BLOG_IMAGE.append('static/assets/images/blog/' + str(result[i][5]))
        MONTHNAME.append(result[i][6])
        year.append(result[i][7])
        day.append(result[i][8])
        BLOG_URL.append(result[i][9])
        length.append(i)
    cur.close()
    conn.close()
    if  'userid' in session:
        sesss_name=session['name']
        user_id=session['userid']
        rollid=session['rollid']
        return render_template('blog.html',BLOG_URL=BLOG_URL,sesss_name=sesss_name,user_id=user_id,length=length,blog_len=blog_len, BLOG_ID=BLOG_ID, HEADING=HEADING,DESCRIPTION=DESCRIPTION,AUTHOR=AUTHOR,BLOG_IMAGE=BLOG_IMAGE,MONTHNAME=MONTHNAME,year=year,day=day,title="Blog")
    else:
        user_id=""
        return render_template('blog.html',BLOG_URL=BLOG_URL,user_id=user_id,length=length,blog_len=blog_len, BLOG_ID=BLOG_ID, HEADING=HEADING,DESCRIPTION=DESCRIPTION,AUTHOR=AUTHOR,BLOG_IMAGE=BLOG_IMAGE,MONTHNAME=MONTHNAME,year=year,day=day,title="Blog")


# ====================================================================================
# ================================Blog Listing====================================================
@app.route('/blog_listing',methods=["GET","POST"])
def blog_listing():
    if 'id' in session:
        if session['role'] == 'admin':
            conn, cur = connection()
            cur.execute("Select BLOG_ID,HEADING,DESCRIPTION,AUTHOR,DATE,BLOG_IMAGE,MONTHNAME(DATE), year(DATE), day(DATE),BLOG_URL from blog order by BLOG_ID desc")
            result=cur.fetchall()
            blog_len=len(result)
            length=[]
            BLOG_ID=[]
            HEADING=[]
            DESCRIPTION=[]
            AUTHOR=[]
            BLOG_IMAGE=[]
            MONTHNAME=[]
            year=[]
            day=[]
            BLOG_URL=[]
            for i in range(len(result)):
                BLOG_ID.append(result[i][0])
                HEADING.append(result[i][1])
                DESCRIPTION.append(result[i][2])
                AUTHOR.append(result[i][3])
                BLOG_IMAGE.append('static/assets/images/blog/' + str(result[i][5]))
                MONTHNAME.append(result[i][6])
                year.append(result[i][7])
                day.append(result[i][8])
                BLOG_URL.append(result[i][9])
                length.append(i)
            cur.close()
            if  'userid' in session:
                sesss_name=session['name']
                user_id=session['userid']
                rollid=session['rollid']
                return render_template('blog_listing.html',sesss_name=sesss_name,user_id=user_id,length=length,BLOG_URL=BLOG_URL,blog_len=blog_len, BLOG_ID=BLOG_ID, HEADING=HEADING,DESCRIPTION=DESCRIPTION,AUTHOR=AUTHOR,BLOG_IMAGE=BLOG_IMAGE,MONTHNAME=MONTHNAME,year=year,day=day,title="Blog")
            else:
                user_id=""
                return render_template('blog_listing.html',user_id=user_id,length=length,BLOG_URL=BLOG_URL,blog_len=blog_len, BLOG_ID=BLOG_ID, HEADING=HEADING,DESCRIPTION=DESCRIPTION,AUTHOR=AUTHOR,BLOG_IMAGE=BLOG_IMAGE,MONTHNAME=MONTHNAME,year=year,day=day,title="Blog")
    return redirect('/')
# ================================= Edit-Blog ============================================
@app.route("/edit_blog/<id>")
def edit_blog(id):
    if 'id' in session:
        if session['role'] == 'admin':
            if request.method == 'GET':
                conn, cur = connection()
                val = cur.execute(
                    "SELECT HEADING,DESCRIPTION,AUTHOR,DATE,BLOG_IMAGE,MONTHNAME(DATE), year(DATE), day(DATE)  FROM blog where BLOG_ID='{}'".format(
                        id))
                result = cur.fetchall()
                length = len(result)
                updateid = id
                HEADING = result[0][0]
                DESCRIPTION = (result[0][1])
                AUTHOR = result[0][2]
                DATE = result[0][3]
                MONTHNAME = result[0][5]
                year = result[0][6]
                day = result[0][7]
                BLOG_IMAGE = 'static/assets/images/blog/' + str(result[0][4])
                if 'userid' in session:
                    sesss_name = session['name']
                    user_id = session['userid']
                    rollid = session['rollid']
                    return render_template('edit_blog.html', id=updateid, sesss_name=sesss_name, user_id=user_id, length=length,
                                           MONTHNAME=MONTHNAME, year=year, day=day, HEADING=HEADING, DESCRIPTION=DESCRIPTION,
                                           AUTHOR=AUTHOR, DATE=DATE, BLOG_IMAGE=BLOG_IMAGE, title="Blog Detail")
                else:
                    user_id = ""
                    return render_template('edit_blog.html', id=updateid, user_id=user_id, length=length, MONTHNAME=MONTHNAME,
                                           year=year, day=day, HEADING=HEADING, DESCRIPTION=DESCRIPTION, AUTHOR=AUTHOR,
                                           DATE=DATE, BLOG_IMAGE=BLOG_IMAGE, title="Blog Detail")
    return redirect('/')

# ===========================================================================================
@app.route("/blog_detail/<id>")
def blog_detail(id):
    conn, cur = connection()
    val = cur.execute(
                "SELECT HEADING,DESCRIPTION,AUTHOR,DATE,BLOG_IMAGE,MONTHNAME(DATE), year(DATE), day(DATE)  FROM blog where BLOG_URL='{}'".format(
                    id))
    result = cur.fetchall()
    HEADING = []
    DESCRIPTION = []
    AUTHOR = []
    DATE = []
    BLOG_IMAGE = []
    MONTHNAME = []
    day = []
    year = []
    length = len(result)
    for i in range(len(result)):
        HEADING.append(result[i][0])
        DESCRIPTION.append(result[i][1])
        AUTHOR.append(result[i][2])
        DATE.append(result[i][3])
        MONTHNAME.append(result[i][5])
        year.append(result[i][6])
        day.append(result[i][7])
        BLOG_IMAGE.append('../static/assets/images/blog/' + str(result[i][4]))
    if 'userid' in session:
        sesss_name = session['name']
        user_id = session['userid']
        rollid = session['rollid']
        return render_template('blog-detail.html', sesss_name=sesss_name, user_id=user_id, length=length,
                               MONTHNAME=MONTHNAME, year=year, day=day, HEADING=HEADING, DESCRIPTION=DESCRIPTION,
                               AUTHOR=AUTHOR, DATE=DATE, BLOG_IMAGE=BLOG_IMAGE, title="Blog Detail")
    else:
        user_id = ""
        return render_template('blog-detail.html', user_id=user_id, length=length, MONTHNAME=MONTHNAME, year=year,
                               day=day, HEADING=HEADING, DESCRIPTION=DESCRIPTION, AUTHOR=AUTHOR, DATE=DATE,
                               BLOG_IMAGE=BLOG_IMAGE, title="Blog Detail")
    #return redirect('/')


#blog ode end***********************************************


#@app.route('/tutor_dashboard', methods=['GET', 'POST'])

# def tutor_dashboard():
#     if 'id' in session:
#         if session['role'] == 'tutor':
#             # Student have not accepted/rejected the schedule yet
#             print(session['id'])
#             conn, cur = connection()
#             cur.execute(
#                 "SELECT TrialClassId, StudentId, SkillId FROM trialclasses WHERE TutorId = '{}' AND Converted = -1 ".format(
#                     session['id']))
#             pending1_classes = cur.fetchall()
#             pending1_data = []
#             for i in range(len(pending1_classes)):
#                 pending1_class_detail = []

#                 cur.execute("SELECT Name FROM studentlogin WHERE StudentId = '{}' ".format(
#                     pending1_classes[i][1]))
#                 sname = cur.fetchone()
#                 pending1_class_detail.append(sname[0])

#                 cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
#                     pending1_classes[i][2]))
#                 subject = cur.fetchone()
#                 pending1_class_detail.append(subject[0])

#                 cur.execute("SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'".format(
#                     pending1_classes[i][0]))
#                 start_date = cur.fetchone()
#                 pending1_class_detail.append(start_date[0])

#                 cur.execute("SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'".format(
#                     pending1_classes[i][0]))
#                 sid = cur.fetchall()
#                 cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(sid[0][0]))
#                 class_time = cur.fetchall()
#                 pending1_class_detail.append(str(class_time[0][0]))

#                 pending1_data.append(pending1_class_detail)

#             no_of_pending1_classes = len(pending1_data)

#             return render_template('teacher-dasboard.html', pending1_data=pending1_data,
#                                    no_of_pending1_classes=no_of_pending1_classes)
#     return redirect('/')

# Tutor Side(Record of his rejected classes)
@app.route('/rejectedclasses', methods=['GET', 'POST'])
def rejectedclasses():
    if 'id' in session:
        if session['role'] == 'tutor':
            conn, cur = connection()
            cur.execute(
                "SELECT TrialClassId, StudentId, SkillId FROM trialclasses WHERE TutorId = '{}' AND Converted = 0 ".format(
                    session['id']))
            rejected_classes = cur.fetchall()
            rej_data = []
            for i in range(len(rejected_classes)):
                rej_class_detail = []

                cur.execute("SELECT Name FROM studentlogin WHERE StudentId = '{}' ".format(
                    rejected_classes[i][1]))
                sname = cur.fetchone()
                rej_class_detail.append(sname[0])

                cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
                    rejected_classes[i][2]))
                subject = cur.fetchone()
                rej_class_detail.append(subject[0])

                cur.execute("SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'".format(
                    rejected_classes[i][0]))
                start_date = cur.fetchone()
                rej_class_detail.append(start_date[0])
                #print(rejected_classes[i][0],"***********************")
                cur.execute("SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'".format(
                    rejected_classes[i][0]))
                sid = cur.fetchall()
                cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(sid[0][0]))
                class_time = cur.fetchall()
                #print(rejected_classes[i][0],"***********************",class_time)
                rej_class_detail.append(str(class_time[0][0]))

                rej_data.append(rej_class_detail)

            no_of_rejected_classes = len(rej_data)

            return render_template('rejected.html', rej_data=rej_data, no_of_rejected_classes=no_of_rejected_classes)

    return redirect('/')


# Tutor has not created schedule of the classes
@app.route('/pendingclasses', methods=['GET', 'POST'])
def pendingclasses():
    if 'id' in session:
        if session['role'] == 'tutor':
            conn, cur = connection()

            cur.execute(
                "SELECT TrialClassId, StudentId, SkillId FROM trialclasses WHERE TutorId = '{}' AND Converted IS NULL ".format(
                    session['id']))
            pending_classes = cur.fetchall()
            pending_data = []
            for i in range(len(pending_classes)):
                pending_class_detail = []

                cur.execute("SELECT Name FROM studentlogin WHERE StudentId = '{}' ".format(
                    pending_classes[i][1]))
                sname = cur.fetchone()
                pending_class_detail.append(sname[0])

                cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
                    pending_classes[i][2]))
                subject = cur.fetchone()
                pending_class_detail.append(subject[0])

                cur.execute("SELECT Date from trialclasses WHERE TrialClassId ='{}'".format(
                    pending_classes[i][0]))
                trialclass_date = cur.fetchone()
                pending_class_detail.append(trialclass_date[0])

                cur.execute("SELECT SlotId from  trialclasses WHERE TrialclassId = '{}'".format(
                    pending_classes[i][0]))
                sid = cur.fetchall()
                cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(sid[0][0]))
                class_time = cur.fetchall()
                pending_class_detail.append(str(class_time[0][0]))

                pending_class_detail.append(pending_classes[i][0])
                print(pending_classes[i][0])

                pending_data.append(pending_class_detail)

            no_of_pending_classes = len(pending_data)

            return render_template('pending.html', pending_data=pending_data, no_of_pending_classes=no_of_pending_classes)
    return redirect('/')

@app.route('/requestedchanges', methods=['GET', 'POST'])
def requestedchanges():
    if 'id' in session:
        if session['role'] == 'tutor':
    # Request for Changes

            conn, cur = connection()
            cur.execute(
                "SELECT TrialClassId, StudentId, SkillId FROM trialclasses WHERE TutorId = '{}' AND Converted = 2 ".format(
                    session['id']))
            change_request_classes = cur.fetchall()
            change_request_data = []
            for i in range(len(change_request_classes)):
                cr_class_detail = []

                cur.execute(
                    "SELECT Name FROM studentlogin WHERE StudentId = '{}' ".format(
                        change_request_classes[i][1]))
                sname = cur.fetchone()
                cr_class_detail.append(sname[0])

                cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
                    change_request_classes[i][2]))
                subject = cur.fetchone()
                cr_class_detail.append(subject[0])

                cur.execute("SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'".format(
                    change_request_classes[i][0]))
                start_date = cur.fetchone()
                cr_class_detail.append(start_date[0])

                cur.execute("SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'".format(
                    change_request_classes[i][0]))
                sid = cur.fetchall()
                cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(
                    sid[0][0]))
                class_time = cur.fetchall()
                cr_class_detail.append(str(class_time[0][0]))

                cr_class_detail.append(change_request_classes[i][0])

                change_request_data.append(cr_class_detail)

            no_of_cr_classes = len(change_request_data)

            return render_template('change-reqest.html', change_request_data=change_request_data,
                                   no_of_cr_classes=no_of_cr_classes)
    return redirect('/')


# Tutor Making the Schedule
@app.route('/schedule_maker/<int:TrialClassId>', methods=['GET', 'POST'])
def schedule_maker(TrialClassId):
    if 'id' in session:
        if session['role'] == 'tutor':
            if request.method == 'GET':
                conn, cur = connection()
                cur.execute("Select * from days")
                days = cur.fetchall()
                return render_template('make_schedule.html', days=days)

            if request.method == 'POST':
                dayid = request.form['day']
                slottime = request.form['slottime']
                startdate = request.form['startDate']
                no_of_classes = request.form['noOfClasses']
                print(request.form.getlist('topic'))
                topiclist = request.form.getlist('topic')
                # added by rishabh 4-5-2021
                totime ='00:00:00'
                print(dayid,"dayid",slottime,"slottime",startdate,"startdate",)

                conn, cur = connection()
                cur.execute("SELECT SlotId FROM tutorslots WHERE dayid='{}' and FromTime='{}' and TutorId='{}'".format(
                    dayid, slottime, session['id']))
                result = cur.fetchone()

                if result is None:
                    cur.execute("Insert INTO tutorslots(TutorId,DayId,FromTime, ToTime) Values('{}','{}','{}','{}')".format(
                        session['id'], dayid, slottime,totime ))
                conn.commit()

                conn, cur = connection()
                cur.execute("SELECT SlotId FROM tutorslots WHERE dayid='{}' and FromTime='{}' and TutorId='{}'".format(
                    dayid, slottime, session['id']))
                slotid = cur.fetchone()

                cur.execute(
                    "Insert INTO tutorschedule(TrialClassId,NoOfClasses,StartDate,SlotId) Values('{}','{}','{}','{}')".format(
                        TrialClassId, no_of_classes, startdate, slotid[0]))
                conn.commit()

                print("Insert INTO tutorschedule(TrialClassId,NoOfClasses,StartDate) Values('{}','{}','{}')".format(
                    TrialClassId, no_of_classes, startdate))
                conn, cur = connection()

                cur.execute("SELECT ScheduleId from tutorschedule WHERE TrialClassId='{}'".format(
                    TrialClassId))

                print("SELECT ScheduleId from tutorschedule WHERE TrialClassId='{}'".format(
                    TrialClassId))
                ScheduleId = cur.fetchone()
                print(ScheduleId)

                conn, cur = connection()

                for i in range(int(no_of_classes)):
                    cur.execute("SET foreign_key_checks = 0")
                    cur.execute("INSERT INTO scheduledetails(ScheduleId,Topic) VALUES('{}','{}')".format(
                        ScheduleId[0], topiclist[i]))
                conn.commit()

                conn, cur = connection()
                cur.execute("UPDATE trialClasses SET converted = -1 WHERE TrialclassId = '{}' ".format(
                    TrialClassId))
                conn.commit()

                conn, cur = connection()
                cur.execute(
                    "SELECT S.Name, S.Email, SK.SkillName, T.Name FROM studentlogin S JOIN trialclasses TC ON S.StudentId = TC.StudentID JOIN skills SK ON TC.skillId = SK.skillId JOIN tutordetails T ON T.TutorId = TC.TutorId WHERE TrialClassId = '{}' ".format(
                        TrialClassId))

                mail_data = cur.fetchall()
                subject = 'Schedule Generated!!'
                to = mail_data[0][1]
                body1 = 'Hi, ' + str(mail_data[0][0])
                body2 = 'Your Schedule for the course ' + str(mail_data[0][2]) + ' by ' + str(
                    mail_data[0][3]) + ' has been created.'
                body3 = 'Login to your Glixcel Account to see the Schedule.'
                body = "{}\n{}\n{}\n".format(body1, body2, body3)
                send_email(subject, to, body)

                flash('Schedule has been sent to the student successfully!!')
                flash("Success")
                flash("success")
                return redirect(url_for('tutor_dashboard'))

            return render_template('make_schedule.html')
    return redirect('/')


# Cheching for slot Availability while generating the schedule
@app.route('/checkslotavailability', methods=['GET', 'POST'])
def checkslotavailability():
    # session['id']=1
    conn, cur = connection()
    dayid = request.form['did']
    slottime = request.form['slottime']
    startdate = request.form['startDate']

    cur.execute("SELECT SlotId from tutorslots where TutorId='{}' and DayId='{}' and FromTime='{}'".format(
        session['id'], dayid, slottime))
    result = cur.fetchall()
    if result:
        cur.execute("SELECT * from trialclasses where TutorId='{}' and slotId='{}' and Date='{}'".format(
            session['id'], result[0][0], startdate))
        result1 = cur.fetchall()
        if result1 is None:
            cur.execute("SELECT * from myclassesslots where slotId='{}' and Date='{}'".format(
                result[0][0], startdate))
            result2 = cur.fetchall()
            if result2:
                return jsonify({'res': 'exists'})
            else:
                return jsonify({'res': 'empty'})
        else:
            return jsonify({'res': 'exists'})
    else:
        return jsonify({'res': 'empty'})


@app.route('/editschedule/<int:TrialClassId>', methods=['GET', 'POST'])
def editschedule(TrialClassId):
    # if request.method == 'GET':
    if 'id' in session:
        if session['role'] == 'tutor':

            conn, cur = connection()

            cur.execute(
                "SELECT ScheduleId, NoOfClasses, StartDate, SlotId FROM tutorschedule WHERE TrialClassId = '{}' ".format(
                    TrialClassId))
            details = cur.fetchall()
            print(details)

            cur.execute("SELECT RequestedChanges FROM tutorschedule WHERE TrialClassId = '{}' ".format(
                TrialClassId))
            query = cur.fetchall()

            cur.execute(
                "SELECT D.DayName, TS.FromTime FROM tutorslots TS JOIN days D ON TS.DayId = D.DayID WHERE SlotId = '{}' ".format(
                    details[0][3]))
            result = cur.fetchall()
            print(result)
            class_time = str(result[0][1])

            cur.execute("SELECT Topic FROM scheduledetails WHERE ScheduleId = '{}' ".format(
                details[0][0]))
            topic_list = cur.fetchall()
            print(topic_list)

            start_date = details[0][2]

            if request.method == 'POST':

                conn, cur = connection()
                no_of_classes = request.form['noOfClasses']
                print(no_of_classes)
                topics = request.form.getlist('topic')
                print(request.form.getlist('topic'))

                cur.execute("UPDATE tutorschedule SET NoOfClasses = '{}' WHERE TrialClassId = '{}' ".format(
                    no_of_classes, TrialClassId))
                conn.commit()

                conn, cur = connection()
                cur.execute("SELECT ScheduleId from tutorschedule WHERE TrialClassId = '{}' ".format(
                    TrialClassId))
                sch_Id = cur.fetchall()
                print(sch_Id)

                cur.execute("DELETE from scheduledetails WHERE ScheduleId = '{}' ".format(
                    sch_Id[0][0]))
                conn.commit()

                conn, cur = connection()

                for i in range(int(no_of_classes)):
                    cur.execute("SET foreign_key_checks = 0")
                    cur.execute("INSERT INTO scheduledetails(ScheduleId,Topic) VALUES('{}','{}')".format(
                        sch_Id[0][0], topics[i]))
                conn.commit()

                conn, cur = connection()
                cur.execute("UPDATE trialclasses SET converted = -1 WHERE TrialClassId = '{}' ".format(
                    TrialClassId))
                conn.commit()

                cur.execute(
                    "SELECT S.Name, S.Email, SK.SkillName, T.Name FROM studentlogin S JOIN trialclasses TC ON S.StudentId = TC.StudentID JOIN skills SK ON TC.skillId = SK.skillId JOIN tutordetails T ON T.TutorId = TC.TutorId WHERE TrialClassId = '{}' ".format(
                        TrialClassId))

                mail_data = cur.fetchall()
                subject = 'Schedule Edited!!'
                to = mail_data[0][1]
                body1 = 'Hi, ' + str(mail_data[0][0])
                body2 = 'Your Schedule for the course ' + str(mail_data[0][2]) + ' by ' + str(
                    mail_data[0][3]) + ' has been edited.'
                body3 = 'Login to your Glixcel Account to see the Changes.'
                body = "{}\n{}\n{}\n".format(body1, body2, body3)
                send_email(subject, to, body)

                flash('Edited Schedule has been sent to the student successfully!!')
                flash("Success")
                flash("success")
                return redirect(url_for('tutor_dashboard'))

            return render_template('edit_schedule.html', details=details, result=result, topic_list=topic_list,
                                   class_time=class_time, start_date=start_date, query=query)
    return redirect('/')


#Listing Of Tutor MyClasses
#Listing Of Tutor MyClasses
@app.route('/tutor_myclasses', methods = ['GET', 'POST'])
def tutor_myclasses():
    if 'id' in session:
        if session['role'] == 'tutor':
            conn, cur = connection()
            cur.execute("SELECT TC.StudentId, TC.SkillId, TS.ScheduleId FROM myclasses MC JOIN tutorschedule TS ON MC.ScheduleId = TS.ScheduleId JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassID WHERE TutorId = '{}' ".format(
                session['id']))
            detail = cur.fetchall()

            my_class_data = []
            for i in range(len(detail)):
                m_data = []

                cur.execute("SELECT Name FROM studentlogin WHERE StudentId = '{}' ".format(
                    detail[i][0]))
                Tname = cur.fetchone()
                m_data.append(Tname[0])

                cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
                    detail[i][1]))
                Subject = cur.fetchone()
                m_data.append(Subject[0])

                cur.execute("SELECT StartDate FROM tutorschedule WHERE scheduleId = '{}' ".format(
                    detail[i][2]))
                start_date = cur.fetchone()
                m_data.append(start_date[0])

                #################write the Code for classes left#################
                cur.execute("SELECT NoOfClasses FROM tutorschedule WHERE scheduleId = '{}' ".format(
                    detail[i][2]))
                no_of_classes = cur.fetchone()
                m_data.append(no_of_classes[0])

                cur.execute("SELECT MyClassId FROM myclasses WHERE scheduleId = '{}' ".format(
                    detail[i][2]))
                mid = cur.fetchone()
                m_data.append(mid[0])

                my_class_data.append(m_data)


            no_of_classes = len(my_class_data)


            return render_template('tutor-my-class.html', my_class_data = my_class_data, no_of_classes = no_of_classes)
    return redirect('/')

# @app.route('/tutor_myclasses_detail/<int:MyClassId>', methods = ['GET', 'POST'])
# def tutor_myclasses_detail(MyClassId):
#     if 'id' in session:
#         if session['role'] == 'tutor':

#             conn, cur = connection()

#             cur.execute("SELECT ScheduleId FROM myclasses WHERE MyClassId = '{}' ".format(
#                 MyClassId))
#             sch_Id = cur.fetchone()

#             cur.execute(
#                 "SELECT SL.Name, TS.NoOfClasses from tutorschedule TS JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassId JOIN studentlogin SL ON TC.StudentId = SL.StudentId WHERE ScheduleId = '{}' ".format(
#                 sch_Id[0]))
#             data = cur.fetchone()   #data[0] = student Name and data[1] = No of classes

#             cur.execute(
#                 "SELECT SkillName FROM Skills S JOIN trialclasses TC ON S.SkillId = TC.SkillId JOIN tutorschedule TS ON TC.TrialClassId = TS.TrialClassId JOIN myclasses MYC ON TS.ScheduleId = MYC.ScheduleId WHERE MYC.MyClassId = '{}' ".format(
#                 MyClassId))
#             subject = cur.fetchone()

#             cur.execute(
#                 "SELECT SlotId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
#                 MyClassId))
#             sid = cur.fetchall()

#             cur.execute(
#                 "SELECT FromTime FROM tutorslots WHERE SlotId = '{}' ".format(
#                 sid[0][0]))
#             class_time = cur.fetchall()
#             class_time = str(class_time[0][0])

#             cur.execute("SELECT D.DayName FROM tutorslots TS JOIN days D ON TS.DayId = D.DayId WHERE TS.SlotId = '{}' ".format(
#                 sid[0][0]))
#             class_day = cur.fetchall()

#             cur.execute("SELECT Date FROM myclassesslots WHERE MyClassId = '{}' ".format(
#                 MyClassId))
#             class_date = cur.fetchall()

#             cur.execute("SELECT Topic FROM Scheduledetails WHERE ScheduleId = '{}' ".format(
#                     sch_Id[0]))
#             topic_list = cur.fetchall()

#             cur.execute("SELECT MeetingId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
#                 MyClassId))
#             meet_Id = cur.fetchall()
#             print(meet_Id)

#             if meet_Id[0][0] is None:
#                 flag = 0
#                 print(flag)
#             else:
#                 flag = 1

#             session['Myclassid'] = MyClassId

#             return render_template('tutor-my-class-detail.html', data = data, subject = subject, topic_list = topic_list, class_date = class_date, class_time = class_time, meet_Id = meet_Id, flag = flag)
#     return redirect('/')



# Tutor Side(Upload class link)


@app.route('/upload_meeting_link', methods = ['GET', 'POST'])
def upload_meeting_link():
    meeting_link = request.form['meeting_link']
    conn, cur = connection()

    cur.execute("UPDATE myclassesslots SET MeetingId = '{}' WHERE MyClassId = '{}' ".format(
       meeting_link, session['Myclassid'] ))
    conn.commit()

    return jsonify({'res': 'done'})

#Tutor Side(Upload class files link)
@app.route('/upload_classfiles_link', methods = ['GET', 'POST'])
def upload_classfiles_link():
    class_file_link = request.form['classfiles_link']
    conn, cur = connection()

    cur.execute("UPDATE myclassesslots SET ClassNotes = '{}' WHERE MyClassId = '{}' ".format(
       class_file_link, session['Myclassid'] ))
    conn.commit()

    return jsonify({'res': 'done'})


# TrialClass Listing Student Side
@app.route('/trialclassesrecord', methods=['GET', 'POST'])
def trialclassesrecord():
    if 'id' in session:
        if session['role'] == 'student':

            conn, cur = connection()
            cur.execute(
                "SELECT TrialClassId,TutorId,SkillId,SlotId FROM Trialclasses WHERE StudentId='{}' AND Converted IN (-1,2) ".format(
                    session['id']))
            tclasses = cur.fetchall()
            print(tclasses)
            trial_class_data = []
            for i in range(len(tclasses)):

                trial_class_info = []
                print(tclasses[i][1])
                cur.execute("SELECT Name from tutordetails WHERE TutorId='{}'".format(tclasses[i][1]))
                Tname = cur.fetchone()
                print(Tname[0])
                trial_class_info.append(Tname[0])

                cur.execute("SELECT SkillName from skills WHERE SkillId ='{}'".format(tclasses[i][2]))
                subject = cur.fetchone()
                trial_class_info.append(subject[0])

                cur.execute("SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'".format(
                    tclasses[i][0]))
                start_date = cur.fetchone()
                print("start_date", start_date)
                if start_date is not None:
                    trial_class_info.append(start_date[0])
                else:
                    trial_class_info.append("No Data Available")

                cur.execute("SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'".format(tclasses[i][0]))
                sid = cur.fetchall()
                print(sid)

                if sid == [] or sid == ():
                    trial_class_info.append("No Data Available")


                else:
                    cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(sid[0][0]))
                    class_time = cur.fetchall()
                    print(class_time)
                    print(str(class_time[0][0]))
                    trial_class_info.append(str(class_time[0][0]))

                cur.execute("SELECT NoOfClasses from tutorschedule WHERE TrialClassId ='{}'".format(tclasses[i][0]))
                no_of_classes = cur.fetchone()
                if no_of_classes is not None:
                    trial_class_info.append(no_of_classes[0])
                else:
                    trial_class_info.append("No Data Available")

                trial_class_info.append(tclasses[i][0])

                trial_class_data.append(trial_class_info)

            no_of_trial_classes = len(trial_class_data)

            return render_template('schedule_table.html', trial_class_data=trial_class_data,
                                   no_of_trial_classes=no_of_trial_classes)
    return redirect('/')

#Student Side(To view Schedule created by tutor)
@app.route("/view_schedule/<int:TrialClassId>",methods=['GET','POST'])
def view_schedule(TrialClassId):
    if 'id' in session:
        if session['role'] == 'student':
            conn,cur = connection()
            cur.execute("SELECT TutorId, SkillId, SlotId FROM trialclasses WHERE TrialClassId = '{}' ".format(
                TrialClassId))
            trial_class_detail = cur.fetchall()
            print(trial_class_detail)

            TrialClassInfo = []

            cur.execute("SELECT Name FROM tutordetails WHERE TutorId = '{}' ".format(
                trial_class_detail[0][0]))
            Tname = cur.fetchone()
            print(Tname[0])
            TrialClassInfo.append(Tname[0])

            cur.execute("SELECT SkillName from skills WHERE SkillId ='{}' ".format(
                trial_class_detail[0][1]))
            subject=cur.fetchone()
            TrialClassInfo.append(subject[0])

            cur.execute("SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'".format(
                TrialClassId))
            start_date=cur.fetchone()
            TrialClassInfo.append(start_date[0])

            cur.execute("SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'".format(
                TrialClassId))
            sid = cur.fetchall()
            print(sid)

            cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(
                sid[0][0]))
            class_time=cur.fetchone()
            # print(str(class_time[0]))
            TrialClassInfo.append(str(class_time[0]))

            cur.execute("SELECT D.DayName from days D JOIN tutorslots ts ON D.DayId = ts.DayId WHERE SlotId ='{}'".format(
                sid[0][0]))
            class_day=cur.fetchone()
            TrialClassInfo.append(class_day[0])

            cur.execute("SELECT NoOfClasses from tutorschedule WHERE TrialClassId ='{}'".format(
                TrialClassId))
            no_of_classes=cur.fetchone()
            TrialClassInfo.append(no_of_classes[0])

            TrialClassInfo.append(trial_class_detail[0][0])

            cur.execute("SELECT CostPerHour FROM tutorskills WHERE TutorId = '{}' AND SkillId = '{}'".format(
                trial_class_detail[0][0], trial_class_detail[0][1]))
            CostPerHour=cur.fetchone()

            TotalCost = no_of_classes[0]*CostPerHour[0]

            cur.execute("SELECT SD.Topic FROM scheduledetails SD JOIN  tutorschedule TS ON SD.ScheduleId = TS.ScheduleId WHERE TS.TrialClassId = '{}' ".format(
                TrialClassId))
            topiclist = cur.fetchall()
            print(topiclist)
            print(TrialClassInfo)

            cur.execute("SELECT SD.scheduleId FROM scheduledetails SD JOIN  tutorschedule TS ON SD.ScheduleId = TS.ScheduleId WHERE TS.TrialClassId = '{}' LIMIT 1".format(
                TrialClassId))
            sch_id = cur.fetchall()
            print(sch_id)
            session['schedule_id'] = sch_id[0][0]
            session['TrialClassId'] = TrialClassId
            print(session['schedule_id'])
            print(session['TrialClassId'])

            return render_template('detail.html', TrialClassInfo=TrialClassInfo, TotalCost=TotalCost, topiclist=topiclist,CostPerHour=CostPerHour,sch_id = sch_id )
    return redirect('/')

#When Student Accepts the Schedule
@app.route('/SetPaymentInfo', methods=['GET', 'POST'])
def SetPaymentInfo():
    session['tid'] = request.form['tid']
    session['tcostperhour'] = request.form['costperhour']
    session['skillid'] = request.form['skillid']
    session['TnoOfclasses'] = request.form['NoOfClasses']
    session['Totalcost'] = request.form['Totalcost']
    session['Scheduleid'] = request.form['Scheduleid']

    return jsonify({'res':'done'})

#Before Paying For MyClasses
@app.route('/review_payment_details', methods=['GET', 'POST'])
def review_payment_details():
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()

            cur.execute("SELECT Name FROM tutordetails WHERE Tutorid = '{}' ".format(
                session['tid']))
            tname = cur.fetchall()
            print(tname)

            return render_template('payment_form_myclass.html', tname = tname)

    return redirect('/')

@app.route("/myclassespayment", methods=['GET', 'POST'])
def myclassespayment():

    API_KEY = "ee4efa380b3d757c67d903028468e0b9"
    AUTH_TOKEN = "4242662ab0dfacef442a7cf5f8d9f4f6"
    api = Instamojo(api_key=API_KEY, auth_token=AUTH_TOKEN)

    response = api.payment_request_create(
        amount=session['Totalcost'],
        purpose="Book Trial Class",
        # buyer_name=session['email'],
        send_email=True,
        email=session['email'],
        redirect_url="http://127.0.0.1:5000/coursepayment"
    )
    conn, cur = connection()
    cur.execute("Insert into paymentdetails(PaymentRequestId, Datetime, Status) values('{}',now(),'Pending')".format(
        response['payment_request']['id']
    ))
    conn.commit()

    return redirect(response['payment_request']['longurl'])


# Payment for MyClasses
@app.route('/coursepayment', methods=['GET', 'POST'])
def coursepayment():
    if 'id' in session:
        if session['role'] == 'student':
    # sch = 20
            payment_id = request.args.get('payment_id')
            payment_status = request.args.get('payment_status')
            payment_request_id = request.args.get('payment_request_id')
            email = request.args.get('email')
            conn, cur = connection()
            cur.execute(
                "UPDATE paymentdetails SET Status='{}', PaymentId='{}' where PaymentRequestId='{}'".format(
                    payment_status,
                    payment_id, payment_request_id))
            conn.commit()
            if payment_status == 'Credit':
                cur.execute("INSERT INTO myclasses(ScheduleId, PaymentRequestId, Status) VALUES('{}','{}','{}') ".format(
                    session['Scheduleid'], payment_request_id, payment_status))
                conn.commit()

                conn, cur = connection()
                cur.execute("SELECT TrialClassId FROM tutorschedule WHERE ScheduleId = '{}' ".format(
                    session['Scheduleid']))
                Trialclassid = cur.fetchone()
                cur.execute("UPDATE trialclasses SET Converted = 1 WHERE TrialClassId = '{}' ".format(
                    Trialclassid[0]))
                conn.commit()

                conn, cur = connection()
                cur.execute("SELECT MyClassId FROM myclasses WHERE ScheduleId ='{}' ".format(
                    session['Scheduleid']))
                my_class_Id = cur.fetchone()

                cur.execute("SELECT * FROM tutorschedule WHERE ScheduleId = '{}' ".format(session['Scheduleid']))
                sch_details = cur.fetchone()

                class_date = sch_details[3]
                print(class_date)

                class_dates = []
                class_dates.append(str(class_date))
                for i in range(int(sch_details[2]) - 1):
                    class_date += datetime.timedelta(days=7)
                    class_dates.append(str(class_date))
                print(class_dates)

                # class_dates1 = []
                # for i in range(len(class_dates)):
                #     x = class_dates[i].split('-')
                #     print(x)
                #     st = x[2] + '-' + x[1] + '-' + x[0]
                #     print(st)
                #     class_dates1.append(st)
                #     print("#################",class_dates1)

                for i in range(len(class_dates)):
                    print(class_dates[i])
                    cur.execute("INSERT INTO myclassesslots(MyClassId,Date,SlotId) VALUES('{}', '{}', '{}') ".format(
                        my_class_Id[0], class_dates[i], sch_details[4]))
                conn.commit()
                subject = 'Request For Editing the Course Schedule'
                to = email
                body1 = 'Hi, '
                body2 = 'You have joined the course successfully'
                body = "{}\n{}\n".format(body1, body2)
                send_email(subject, to, body)
                flash("You have joined the course successfully")
                flash("Success")
                flash("success")
                return redirect(url_for('student_myclasses'))
            else:
                flash("Payment Failed!!")
                flash("Failed")
                flash("error")
                return redirect(url_for('trialclassesrecord'))
    return redirect('/')

#Student Side( Rejecting the Schedule)
@app.route('/reject', methods=['GET', 'POST'])
def reject():
    print(session['TrialClassId'])
    conn, cur = connection()
    cur.execute("UPDATE trialclasses SET Converted = 0 WHERE TrialClassId = '{}' ".format(
         session['TrialClassId']))
    conn.commit()

    return jsonify({'res':'done'})

#Student Side (For requesting to change something in Schedule)
@app.route('/changerequest', methods=['GET', 'POST'])
def changerequest():
    if request.method == 'POST':
        query = request.form['query']
        print(query)
        print(session['schedule_id'])
        conn, cur = connection()
        cur.execute("UPDATE tutorschedule SET RequestedChanges = '{}' WHERE ScheduleId = '{}' ".format(
            query, session['schedule_id']))
        conn.commit()

        conn, cur = connection()
        cur.execute("SELECT TrialClassId FROM tutorschedule WHERE ScheduleId = '{}' ".format(
           session['schedule_id']))
        trialId = cur.fetchall()

        cur.execute("UPDATE trialClasses SET converted = 2 WHERE TrialClassId = '{}' ".format(
            trialId[0][0]))
        conn.commit()

        conn, cur = connection()
        cur.execute("SELECT T.Name, T.Email, SK.SkillName, S.Name FROM studentlogin S JOIN trialclasses TC ON S.StudentId = TC.StudentID JOIN skills SK ON TC.skillId = SK.skillId JOIN tutordetails T ON T.TutorId = TC.TutorId WHERE TrialClassId = '{}' ".format(
            trialId[0][0]))

        mail_data = cur.fetchall()
        subject = 'Request For Editing the Course Schedule'
        to = mail_data[0][1]
        body1 = 'Hi, ' + str(mail_data[0][0])
        body2 = 'You have been requested to change the schedule of the course ' + str(mail_data[0][2]) +' by ' + str(mail_data[0][3]) + '.'
        body3 = 'Login to your Glixcel Account to see the request.'
        body = "{}\n{}\n{}\n".format(body1, body2, body3)
        send_email(subject, to, body)



        return jsonify({'res':'done'})


# Listing OF Student Myclasses
@app.route('/student_myclasses', methods=['GET', 'POST'])
def student_myclasses():
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()
            cur.execute(
                "SELECT TC.TutorId, TC.SkillId, TS.ScheduleId, MC.MyClassId FROM myclasses MC JOIN tutorschedule TS ON MC.ScheduleId = TS.ScheduleId JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassID WHERE StudentId = '{}' ".format(
                    session['id']))
            detail = cur.fetchall()

            my_class_data = []
            for i in range(len(detail)):
                m_data = []

                cur.execute("SELECT Name FROM tutordetails WHERE Tutorid = '{}' ".format(
                    detail[i][0]))
                Tname = cur.fetchone()
                m_data.append(Tname[0])

                cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
                    detail[i][1]))
                Subject = cur.fetchone()
                m_data.append(Subject[0])

                cur.execute("SELECT StartDate FROM tutorschedule WHERE scheduleId = '{}' ".format(
                    detail[i][2]))
                start_date = cur.fetchone()
                m_data.append(start_date[0])

                #################write the Code for classes left#################
                cur.execute("SELECT NoOfClasses FROM tutorschedule WHERE scheduleId = '{}' ".format(
                    detail[i][2]))
                no_of_classes = cur.fetchone()
                m_data.append(no_of_classes[0])

                m_data.append(detail[i][3])
                print(detail[i][3])

                my_class_data.append(m_data)

            no_of_classes = len(my_class_data)

            return render_template('student-my-class.html', my_class_data=my_class_data, no_of_classes=no_of_classes)
    return redirect('/')



# @app.route('/student_myclasses_detail/<int:MyClassId>', methods=['GET', 'POST'])
# def student_myclasses_detail(MyClassId):
#     if 'id' in session:
#         if session['role'] == 'student':
#             conn, cur = connection()

#             cur.execute("SELECT ScheduleId FROM myclasses WHERE MyClassId = '{}' ".format(
#                 MyClassId))
#             sch_Id = cur.fetchone()
#             print(sch_Id)

#             cur.execute(
#                 "SELECT TD.Name, TS.NoOfClasses from tutorschedule TS JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassId JOIN tutordetails TD ON TC.TutorId = TD.tutorId WHERE ScheduleId = '{}' ".format(
#                     sch_Id[0]))
#             data = cur.fetchone()  # data[0] = tutor Name and data[1] = No of classes

#             cur.execute(
#                 "SELECT SkillName FROM Skills S JOIN trialclasses TC ON S.SkillId = TC.SkillId JOIN tutorschedule TS ON TC.TrialClassId = TS.TrialClassId JOIN myclasses MYC ON TS.ScheduleId = MYC.ScheduleId WHERE MYC.MyClassId = '{}' ".format(
#                     MyClassId))
#             subject = cur.fetchone()

#             cur.execute("SELECT MeetingId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
#                 MyClassId))
#             meeting_id = cur.fetchall()
#             print(meeting_id)
#             if meeting_id[0][0] is None:
#                 flag = 0
#                 print(flag)
#             else:
#                 flag = 1

#             cur.execute("SELECT Topic FROM Scheduledetails WHERE ScheduleId = '{}' ".format(
#                 sch_Id[0]))
#             topic_list = cur.fetchall()
#             print(topic_list)

#             cur.execute("SELECT Date FROM myclassesslots WHERE MyClassId = '{}' ".format(
#                 MyClassId))
#             class_date = cur.fetchall()

#             cur.execute("SELECT SlotId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
#                 MyClassId))
#             sid = cur.fetchall()
#             print(sid)

#             cur.execute("SELECT FromTime FROM tutorslots WHERE SlotId = '{}' ".format(
#                 sid[0][0]))
#             class_time = cur.fetchall()
#             print(str(class_time[0][0]))
#             class_time = str(class_time[0][0])

#             cur.execute("SELECT ClassNotes FROM myclassesslots WHERE MyClassId = '{}' ".format(
#                 MyClassId))
#             classnoteslink = cur.fetchall()
#             print(classnoteslink[0][0])
#             if classnoteslink[0][0] is None:
#                 flag1 = 0
#                 print(flag)
#             else:
#                 flag1 = 1

#             # if request.method == 'POST':
#             #     rating = request.form['rate']
#             #     review = request.form['review']

#             #     conn, cur = connection()

#             #     cur.execute("SELECT ScheduleId FROM myclasses WHERE MyClassId = '{}' ".format(
#             #     MyClassId))
#             #     sch_Id = cur.fetchone()

#             #     cur.execute("SELECT TD.Tutorid from tutorschedule TS JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassId JOIN tutordetails TD ON TC.TutorId = TD.tutorId WHERE ScheduleId = '{}' ".format(
#             #     sch_Id[0]))
#             #     TID = cur.fetchone()

#             #     cur.execute("SELECT Rating FROM tutorrating WHERE TutorId ='{}' ".format(
#             #         TID[0]))
#             #     all_ratings = cur.fetchall()

#             return render_template('myclass-Details.html', data=data, subject=subject, topic_list=topic_list,
#                                    class_date=class_date, class_time=class_time, meeting_id=meeting_id,
#                                    classnoteslink=classnoteslink, flag=flag, flag1=flag1)
#     return redirect('/')





# shubhangi code added by rishabh 5-5-2021

@app.route('/tutor_sent_schedule_detail/<int:TrialClassId>', methods = ['GET', 'POST'])
def tutor_sent_schedule_detail(TrialClassId):
    if 'id' in session:
        if session['role'] == 'tutor':
            conn,cur = connection()

            cur.execute(
                "SELECT SkillId FROM trialclasses WHERE TrialClassId = '{}' ".
                format(TrialClassId))
            trial_class_detail = cur.fetchall()
            print(trial_class_detail)

            TrialClassInfo = []

            
            cur.execute(
                "SELECT SkillName from skills WHERE SkillId ='{}' "
                    .format(trial_class_detail[0][0]))
            subject=cur.fetchone()
            TrialClassInfo.append(subject[0])

            cur.execute(
                "SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'"
                    .format(TrialClassId))
            start_date=cur.fetchone()
            TrialClassInfo.append(start_date[0])

            cur.execute(
                "SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'"
                    .format(TrialClassId))
            sid = cur.fetchall()
            print(sid)

            cur.execute(
                "SELECT FromTime from tutorslots WHERE SlotId ='{}'"
                    .format(sid[0][0]))
            class_time=cur.fetchone()
            # print(str(class_time[0]))
            TrialClassInfo.append(str(class_time[0]))

            cur.execute(
                "SELECT D.DayName from days D JOIN tutorslots ts ON D.DayId = ts.DayId WHERE SlotId ='{}'"
                    .format(sid[0][0]))
            class_day=cur.fetchone()
            TrialClassInfo.append(class_day[0])

            cur.execute(
                "SELECT NoOfClasses from tutorschedule WHERE TrialClassId ='{}'"
                    .format(TrialClassId))
            no_of_classes=cur.fetchone()
            TrialClassInfo.append(no_of_classes[0])

            TrialClassInfo.append(trial_class_detail[0][0])

            

            cur.execute(
                "SELECT SD.Topic FROM scheduledetails SD JOIN  tutorschedule TS ON SD.ScheduleId = TS.ScheduleId WHERE TS.TrialClassId = '{}' "
                    .format(TrialClassId))
            topiclist = cur.fetchall()
            print(topiclist)
            print(TrialClassInfo)

            

            return render_template('tutor_sent_schedule_detail.html', TrialClassInfo=TrialClassInfo, topiclist=topiclist)
    return redirect('/')


#edit slots
@app.route('/editslots', methods=['GET', 'POST'])
def editslots():
    if request.method == 'POST':
        daydata = request.form['daydata']
        fromdata = request.form['fromdata']
        todata = request.form['todata']
        daylist = daydata.split(',')
        fromlist = fromdata.split(',')
        tolist = todata.split(',')
        print("daydata")
        conn, cur = connection()
        cur.execute(
            "Delete from tutorslots where SlotId NOT IN (Select slotId from trialclasses where tutorId='{}') AND SlotId NOT IN(SELECT TSH.Slotid from tutorschedule TSH JOIN trialclasses TC ON TSH.TrialClassId = TC.TrialClassId WHERE TutorId = '{}') AND TutorId='{}'".format(
           session['id'], session['id'], session['id']))
        conn.commit()
        for i in range(len(daylist)):
            cur.execute("Insert into tutorslots(TutorId, DayId, FromTime, ToTime) values('{}','{}','{}','{}')".format(
                session['id'], daylist[i], fromlist[i], tolist[i]
            ))
            conn.commit()

    return jsonify({'res': 'done'})


#updated shumbhangi added rishabh 5-5-2021


@app.route('/tutor_dashboard', methods = ['GET', 'POST'])
def tutor_dashboard():
    if 'id' in session:
        if session['role'] == 'tutor':
            #Student have not accepted/rejected the schedule yet
            print('session Id is',session['id'])
            conn, cur = connection()
            cur.execute("SELECT TrialClassId, StudentId, SkillId FROM trialclasses WHERE TutorId = '{}' AND Converted = -1 ".format(
                session['id']))
            pending1_classes = cur.fetchall()
            pending1_data = []


            for i in range(len(pending1_classes)):
                pending1_class_detail = []

                cur.execute("SELECT Name FROM studentlogin WHERE StudentId = '{}' ".format(
                    pending1_classes[i][1]))
                sname = cur.fetchone()
                pending1_class_detail.append(sname[0])               
                cur.execute("SELECT SkillName FROM skills WHERE SkillId = '{}' ".format(
                    pending1_classes[i][2]))
                subject = cur.fetchone()
                pending1_class_detail.append(subject[0])

                cur.execute("SELECT StartDate from tutorschedule WHERE TrialClassId ='{}'".format(
                    pending1_classes[i][0]))
                start_date=cur.fetchone()
                pending1_class_detail.append(start_date[0])

                #cur.execute("SELECT SlotId from  tutorschedule WHERE TrialclassId = '{}'".format(
                    #pending1_classes[i][0]))
                #sid = cur.fetchall()
                #cur.execute("SELECT FromTime from tutorslots WHERE SlotId ='{}'".format(sid[0][0]))
                #class_time=cur.fetchall()
                #pending1_class_detail.append(str(class_time[0][0]))

                pending1_class_detail.append(pending1_classes[i][0])

                pending1_data.append(pending1_class_detail)

            no_of_pending1_classes = len(pending1_data)


#Tutor lead generation Abhishek Gautam
            cur.execute("Select * from tutorskills WHERE TutorID ='{}' ".format(
                session['id']
            ))
            tutor_data = cur.fetchall()
            print(tutor_data)
            lead_one=[]
            for i in tutor_data:
                cur.execute("SELECT * FROM studentquery WHERE SkillId = '{}'  ".format(
                    i[1]))
                u=cur.fetchall()
                lead_one=lead_one+u
            
            print(lead_one)
            leads=[] 
            for i in lead_one:
                print(i)
                if str(session["id"]) in i[7:]:
                    pass
                elif str(session["id"]) in str(i[-1]) :
                    pass
                else:
                    leads.append(i)
            if request.method == "POST":
                leads=[]
                for i in lead_one:
                    if str(session["id"]) in i[7:]:
                        pass
                    else:
                        leads.append(i)
                lead_reponse = request.form["lead_response"]
                print("lead reponse is",lead_reponse)
                if 'R'  not in lead_reponse:
                    cur.execute("SELECT * FROM studentquery WHERE  QueryId = '{}' ".format(
                        lead_reponse ))
                    query = cur.fetchall()
                    
                    for i in range(7,12):
                        if query[0][i] == None:
                            tutor_no=i
                            break
                    if tutor_no <12 :
                        if session not in query[0]:
                            key = "tutor" +str(tutor_no-6)
                            cur.execute("UPDATE studentquery SET {} = {} WHERE QueryId = {}; ".format(
                                key,int(session["id"]),int(lead_reponse)
                            ))
                            conn.commit()
                            print("work is done")
                        leads.remove(query[0])
                        queryUrl = "http://192.168.43.2:8000/studentQueryResponse?id="+ str(query[0][0])
                        send_email("Lead", query[0][2],str("accepted please checkout : "+queryUrl))
                    else:
                        leads.remove(query[0])
                else :
                    lead_response=lead_reponse[1:]
                    cur.execute("SELECT * FROM studentquery WHERE  QueryId = '{}' ".format(
                        lead_response ))
                    query = cur.fetchall()
                    
                    cur.execute("Select rejectedTutorId from studentquery Where QueryId ={};".format(
                        int(lead_response)))
                    
                    rejectedTutorId = cur.fetchall()[0]
                    rejectedTutorId = str(rejectedTutorId[0])+","+str(session["id"])
                    cur.execute("UPDATE studentquery SET rejectedTutorId = '{}' WHERE QueryId = '{}' ".format(
                        rejectedTutorId,lead_response)
                    )
                    conn.commit()
                    print("hii")                    
                    
                    print(query)
                    print(leads)
                    leads.remove(query[0])


            return render_template('teacher-dasboard.html',leads=leads, pending1_data = pending1_data, no_of_pending1_classes = no_of_pending1_classes )
    return redirect('/')

@app.route('/studentQueryResponse',methods=['GET','POST'])
def studentQueryResponse():
    conn, cur = connection()
    id= request.args["id"]
    cur.execute("SELECT * FROM studentquery WHERE  QueryId = '{}' ".format(id ))
    query = cur.fetchall()
    tutor_data=[]
    
    for i in query[0][7:12]:
        if i != None:
            cur.execute("SELECT * FROM tutordetails WHERE  TutorId = '{}' ".format(i))
            tutor_data.append(cur.fetchall())

    return render_template('studentQueryResponse.html',tutor_data=tutor_data)





@app.route('/student_myclasses_detail/<int:MyClassId>', methods = ['GET', 'POST'])
def student_myclasses_detail(MyClassId):
    if 'id' in session:
        if session['role'] == 'student':
            conn, cur = connection()
            # Session['id'] = 1

            cur.execute("SELECT ScheduleId FROM myclasses WHERE MyClassId = '{}' ".format(
                MyClassId))
            sch_Id = cur.fetchone()
            print(sch_Id)

            cur.execute("SELECT TD.Name, TS.NoOfClasses from tutorschedule TS JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassId JOIN tutordetails TD ON TC.TutorId = TD.tutorId WHERE ScheduleId = '{}' ".format(
                sch_Id[0]))
            data = cur.fetchone()       #data[0] = tutor Name and data[1] = No of classes


            cur.execute("SELECT SkillName FROM Skills S JOIN trialclasses TC ON S.SkillId = TC.SkillId JOIN tutorschedule TS ON TC.TrialClassId = TS.TrialClassId JOIN myclasses MYC ON TS.ScheduleId = MYC.ScheduleId WHERE MYC.MyClassId = '{}' ".format(
                MyClassId))
            subject = cur.fetchone()

            cur.execute("SELECT MeetingId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
                MyClassId))
            meeting_id = cur.fetchall()
            print(meeting_id)
            if meeting_id[0][0] is None:
                flag = 0
                print(flag)
            else:
                flag = 1


            cur.execute("SELECT Topic FROM Scheduledetails WHERE ScheduleId = '{}' ".format(
                    sch_Id[0]))
            topic_list = cur.fetchall()
            print(topic_list)

            cur.execute("SELECT Date FROM myclassesslots WHERE MyClassId = '{}' ".format(
                MyClassId))
            class_date = cur.fetchall()

            cur.execute("SELECT SlotId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
                MyClassId))
            sid = cur.fetchall()
            print(sid)

            cur.execute("SELECT FromTime FROM tutorslots WHERE SlotId = '{}' ".format(
                sid[0][0]))
            class_time = cur.fetchall()
            print(str(class_time[0][0]))
            class_time = str(class_time[0][0])


            cur.execute("SELECT ClassNotes FROM myclassesslots WHERE MyClassId = '{}' ".format(
                MyClassId))
            classnoteslink = cur.fetchall()
            print(classnoteslink[0][0])
            if classnoteslink[0][0] is None:
                flag1 = 0
                print(flag)
            else:
                flag1 = 1

            #No of Classes Left
            count = data[1]
            for i in range(data[1]):
                if class_date[i][0]<date.today():
                    count-= 1

            # if request.method == 'POST':
            #     rating = request.form['rate']
            #     review = request.form['review']

            #     conn, cur = connection()

            #     cur.execute("SELECT ScheduleId FROM myclasses WHERE MyClassId = '{}' ".format(
            #     MyClassId))
            #     sch_Id = cur.fetchone()

            #     cur.execute("SELECT TD.Tutorid from tutorschedule TS JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassId JOIN tutordetails TD ON TC.TutorId = TD.tutorId WHERE ScheduleId = '{}' ".format(
            #     sch_Id[0]))
            #     TID = cur.fetchone()

            #     cur.execute("SELECT Rating FROM tutorrating WHERE TutorId ='{}' ".format(
            #         TID[0]))
            #     all_ratings = cur.fetchall()

            
            return render_template('myclass-Details.html', data = data, subject = subject, topic_list = topic_list, class_date = class_date, class_time = class_time, meeting_id = meeting_id, classnoteslink = classnoteslink , flag = flag, flag1 = flag1, count = count)
    return redirect('/')


@app.route('/tutor_myclasses_detail/<int:MyClassId>', methods = ['GET', 'POST'])
def tutor_myclasses_detail(MyClassId):
    if 'id' in session:
        if session['role'] == 'tutor':
            conn, cur = connection()

            cur.execute("SELECT ScheduleId FROM myclasses WHERE MyClassId = '{}' ".format(
                MyClassId))
            sch_Id = cur.fetchone()

            cur.execute(
                "SELECT SL.Name, TS.NoOfClasses from tutorschedule TS JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassId JOIN studentlogin SL ON TC.StudentId = SL.StudentId WHERE ScheduleId = '{}' ".format(
                sch_Id[0]))
            data = cur.fetchone()   #data[0] = student Name and data[1] = No of classes
            print(data[1])
            cur.execute(
                "SELECT SkillName FROM Skills S JOIN trialclasses TC ON S.SkillId = TC.SkillId JOIN tutorschedule TS ON TC.TrialClassId = TS.TrialClassId JOIN myclasses MYC ON TS.ScheduleId = MYC.ScheduleId WHERE MYC.MyClassId = '{}' ".format(
                MyClassId))
            subject = cur.fetchone()

            cur.execute(
                "SELECT SlotId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
                MyClassId))
            sid = cur.fetchall()

            cur.execute(
                "SELECT FromTime FROM tutorslots WHERE SlotId = '{}' ".format(
                sid[0][0]))
            class_time = cur.fetchall()
            class_time = str(class_time[0][0])
            print(class_time)
            type(class_time)
            # print(datetime.now())
            # date_time = datetime.datetime.now()
            # print(date_time.time())

            cur.execute("SELECT D.DayName FROM tutorslots TS JOIN days D ON TS.DayId = D.DayId WHERE TS.SlotId = '{}' ".format(
                sid[0][0]))
            class_day = cur.fetchall()

            cur.execute("SELECT Date FROM myclassesslots WHERE MyClassId = '{}' ".format(
                MyClassId))
            class_date = cur.fetchall()
            print(class_date)

            cur.execute("SELECT Topic FROM Scheduledetails WHERE ScheduleId = '{}' ".format(
                    sch_Id[0]))
            topic_list = cur.fetchall()
            print(topic_list)

            cur.execute("SELECT MeetingId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1".format(
                MyClassId))
            meet_Id = cur.fetchall()
            print(meet_Id)

            if meet_Id[0][0] is None:
                flag = 0
                print(flag)
            else:
                flag = 1

            session['Myclassid'] = MyClassId
            print(session['Myclassid'])
            
            #No of Classes Left
            count = data[1]
            for i in range(data[1]):
                if class_date[i][0]<date.today():
                    count-= 1
                    

            return render_template('tutor-my-class-detail.html', data = data, subject = subject, topic_list = topic_list, class_date = class_date, class_time = class_time, meet_Id = meet_Id, flag = flag, count = count)
    return redirect('/')



# code by rishabh
@app.route('/fetchtag', methods=['GET', 'POST'])
def fetchtag():
    if request.method=="POST":
        id = request.form['option']
        print(id)
        conn, cur = connection()
        cur.execute("select * from tags WHERE SkillId = '{}' ".format(
                id))
        sch_Id = cur.fetchall()
        tag_list = []
        for t in sch_Id:
            tag_list.append(t[2])
        return jsonify({'res': tag_list})



# 6-5-2021
#tutor worksheet creation
@app.route('/tutor_worksheet/<int:Classno>', methods = ['GET', 'POST'])
def tutor_worksheet(Classno):
    if 'id' in session:
        if session['role'] == 'tutor':
            conn, cur = connection()
            cur.execute(
                "SELECT ClassId, Date FROM myclassesslots WHERE MyClassId = '{}' "
                    .format(session['Myclassid']))
            data = cur.fetchall()
            print(session['Myclassid'])

            class_info = []

            for i in range(len(data)):
                class_no = []
                class_no.append(data[i][0])
                class_no.append(i+1)
                class_no.append(data[i][1])

                class_info.append(class_no)

            for i in range(len(data)):
                if class_info[i][1] == Classno:
                    c_date = class_info[i][2]
                    break

            print(class_info)

            if request.method == 'POST':
                cno = request.form['class_no']
                c_date = request.form['class_date']
                attendance_sheet_link = request.form['worksheet_attandance']
                video_link = request.form['class_video_link']
                
                for i in range(len(data)):
                    if class_info[i][1] == int(cno):
                        cid = class_info[i][0]
                        print(cid)
                        break

                cur.execute(
                    "UPDATE myclassesslots SET AttendanceSheetLink = '{}', VideoLink = '{}' , TutorAttendanceApproval = 1 WHERE ClassId = '{}' "
                        .format(attendance_sheet_link, video_link, cid))
                conn.commit()

                conn , cur = connection()

                cur.execute(
                    "SELECT TutorAttendanceApproval FROM myclassesslots WHERE MyClassId = '{}' "
                        .format(session['Myclassid']))
                taa = cur.fetchall()

                count = 0
                for i in range(len(data)):
                    if taa[i][0] == 1:
                        count += 1

                if count == len(data):
                    cur.execute(
                        "UPDATE myclasses SET TutorAllWorksheetsApproval = 1 WHERE MyClassId = '{}' "
                            .format(session['Myclassid']))
                    conn.commit()

                return redirect(url_for('tutor_dashboard'))


            return render_template('tutor-worksheet.html',Classno = Classno, c_date = c_date)
    return redirect('/')




@app.route('/tutor_worksheet_detail/<int:MyClassId>', methods = ['GET', 'POST'])
def tutor_worksheet_detail(MyClassId):
    if 'id' in session:
        if session['role'] == 'tutor':

            conn , cur = connection()
            cur.execute(
                "SELECT TS.NoOfClasses FROM tutorschedule TS JOIN myclasses MCL ON TS.ScheduleId = MCL.ScheduleId WHERE MCL.MyClassId = '{}' "
                    .format(MyClassId))
            no_of_classes = cur.fetchone()

            cur.execute(
                "SELECT Date FROM myclassesslots WHERE MyClassId = '{}' AND TutorAttendanceApproval = 1 "
                    .format(MyClassId))
            class_dates = cur.fetchall()

            cur.execute(
                "SELECT AttendanceSheetLink,  VideoLink FROM myclassesslots WHERE MyClassId = '{}' AND TutorAttendanceApproval = 1 "
                    .format(MyClassId))
            links = cur.fetchall()

            cur.execute(
                "SELECT SlotId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1"
                    .format(MyClassId))
            sid = cur.fetchone()

            cur.execute(
                "SELECT DayName, FromTime FROM tutorslots TS JOIN days D ON TS.DayId = D.DayId WHERE TS.SlotId = '{}' "
                    .format(sid[0]))
            day_time = cur.fetchone()
            print(day_time)

            cur.execute(
                "SELECT TutorAttendanceApproval FROM myclassesslots WHERE MyClassId = '{}' "
                    .format(MyClassId))
            taa = cur.fetchall()
            print(taa)
            print(no_of_classes[0])
            no_of_classes_completed = 0
            for i in range(no_of_classes[0]):
                if taa[i][0] == 1:
                    no_of_classes_completed += 1

            cur.execute(
                "SELECT StudentAttendanceApproval FROM myclassesslots WHERE MyClassId = '{}' "
                    .format(MyClassId))
            saa = cur.fetchall()

            return render_template('tutor_work_sheet_details.html', no_of_classes_completed = no_of_classes_completed, class_dates = class_dates, day_time = day_time, taa = taa, saa = saa, links = links)
    return redirect('/')



@app.route('/student_worksheet', methods = ['GET', 'POST'])
def student_worksheet():
    if 'id' in session:
        if session['role'] == 'student':
            # session['id'] = 6
            conn, cur = connection()
            cur.execute(
                "SELECT TC.TutorId, TC.SkillId, TS.ScheduleId, MC.MyClassId FROM myclasses MC JOIN tutorschedule TS ON MC.ScheduleId = TS.ScheduleId JOIN trialclasses TC ON TS.TrialClassId = TC.TrialClassID WHERE StudentId = '{}' AND MC.TutorAllWorksheetsApproval = 1"
                    .format(session['id']))
            detail = cur.fetchall()
            print(detail)

            my_class_data = []
            for i in range(len(detail)):
                m_data = []

                cur.execute(
                    "SELECT Name FROM tutordetails WHERE Tutorid = '{}' "
                        .format(detail[i][0]))
                Tname = cur.fetchone()
                m_data.append(Tname[0])

                cur.execute(
                    "SELECT SkillName FROM skills WHERE SkillId = '{}' "
                        .format(detail[i][1]))
                Subject = cur.fetchone()
                m_data.append(Subject[0])

                cur.execute(
                    "SELECT StartDate FROM tutorschedule WHERE scheduleId = '{}' "
                        .format(detail[i][2]))
                start_date = cur.fetchone()
                m_data.append(start_date[0])
                m_data.append(detail[i][3])

                my_class_data.append(m_data)

            print(my_class_data)

            length = len(my_class_data)

            return render_template('student_work_sheet.html', my_class_data = my_class_data, length = length)
    return redirect('/')



@app.route('/student_worksheet_detail/<int:MyClassId>', methods = ['GET', 'POST'])
def student_worksheet_detail(MyClassId):
    if 'id' in session:
        if session['role'] == 'student':
            conn , cur = connection()
            
            cur.execute(
                "SELECT Date FROM myclassesslots WHERE MyClassId = '{}' AND TutorAttendanceApproval = 1 "
                    .format(MyClassId))
            class_dates = cur.fetchall()

            cur.execute(
                "SELECT AttendanceSheetLink  FROM myclassesslots WHERE MyClassId = '{}' AND TutorAttendanceApproval = 1 "
                    .format(MyClassId))
            link = cur.fetchall()

            cur.execute(
                "SELECT SlotId FROM myclassesslots WHERE MyClassId = '{}' LIMIT 1"
                    .format(MyClassId))
            sid = cur.fetchone()

            cur.execute(
                "SELECT DayName, FromTime FROM tutorslots TS JOIN days D ON TS.DayId = D.DayId WHERE TS.SlotId = '{}' "
                    .format(sid[0]))
            day_time = cur.fetchone()
            print(day_time)

            cur.execute(
                "SELECT TutorAttendanceApproval FROM myclassesslots WHERE MyClassId = '{}' "
                    .format(MyClassId))
            taa = cur.fetchall()

            cur.execute(
                "SELECT ClassId FROM myclassesslots WHERE MyClassId = '{}' "
                    .format(MyClassId))
            cid = cur.fetchall()
            print(cid)

            no_of_classes_completed = 0
            for i in range(len(class_dates)):
                if taa[i][0] == 1:
                    no_of_classes_completed += 1

            # cur.execute(
            #     "SELECT StudentAttendanceApproval FROM myclassesslots WHERE MyClassId = '{}' "
            #         .format(MyClassId))
            # saa = cur.fetchall()

            return render_template('student_work_sheet_details.html', no_of_classes_completed = no_of_classes_completed, class_dates = class_dates, link = link, day_time = day_time, cid = cid)    
    return redirect('/')


@app.route('/updateapproval', methods = ['GET', 'POST'])
def updateapproval():
    cid = request.form['cid']
    approved_result = request.form['approvalresult']
    print(request.form['cid'])
    print(request.form['approvalresult'])
    print(type(approved_result))
    ar = int(approved_result)
    # class_id = int(cid)


    print(type(ar))

    conn, cur = connection()
    cur.execute(
        "UPDATE myclassesslots SET StudentAttendanceApproval = '{}' WHERE ClassId = '{}' "
            .format(ar,cid))
    conn.commit()

    return jsonify({'res':'done'})


#Teacher_search engine AKA

@app.route('/t123',methods=['GET','POST'])
def teacherSearch():
    #conn = mysql.connector.connect()
    #cursor = conn.cursor()
    conn, cur = connection()
    cur.execute("SELECT * from skills " )
    conn.commit()
    skills = cur.fetchall()
    if request.method == 'POST':
        
        name = request.form['name']
        contact = request.form['contact']
        email = request.form['email']
        skillid = request.form['subject']
        amount = request.form['amount']
        desc = request.form['desc']

        
       # print("Skillid is",skillid)
        
        
        cur.execute(
            "INSERT INTO studentquery (studentname, studentemail,skillid,contactno,query,pricerange) values('{}','{}','{}','{}','{}','{}')"
            .format(name, email,skillid,contact,desc,amount))
        conn.commit()
        

        cur.execute("SELECT * from tutorskills WHERE skillid ='{}' " .format(skillid))
        conn.commit()

        data=cur.fetchall()
        lang_filter = ['hindi','english']
        gender_filter = ['male','female']
        desc = list(map(str,desc.split(" ")))
        key_words =[]
        for i in desc:
            if i.lower() in lang_filter:
                key_words.append(i)
            if i.lower in gender_filter:
                key_words.append(i)
        print(data)

    return render_template('t123.html',skills=skills)


from pika import channel
from pika.spec import Queue

def RBserver_sender(QueueName,Data):
    try :
        import pika

    except Exception as e:
        print(e)

    class MetaClass(type):
        _instance ={}
        def __call__(cls, *args, **kwargs) :
            if cls not in cls._instance:
                cls._instance[cls] = super(MetaClass,cls).__call__(*args,**kwargs)
                return cls._instance[cls]

    class rabbit(metaclass = MetaClass):
        def __init__(self,QueueName) :
            self._connection = pika.BlockingConnection(
                                pika.ConnectionParameters(host="localhost")
                                )
            self._channel =self._connection.channel()
            self.queue  = QueueName
            self._channel.queue_declare(queue=self.queue)
        def publish(self,payload={}):
            self._channel.basic_publish(exchange="",
                                        routing_key=QueueName,
                                        body=str(payload))
            print("Message Published")
            self._connection.close()
    if Data != None:
        server = rabbit(QueueName)
        server.publish(Data)            



@app.route('/schedular', methods = ['GET', 'POST'])
def schedular():
    conn, cur = connection()
    
    if request.method == "POST":
        conn, cur = connection()
        body = request.form["body"]
        QueueName = "hello" 
        data={"Data":body}
        RBserver_sender(QueueName,data)
        
    return render_template("schedular.html")
@app.route('/schedular2', methods = ['GET', 'POST'])
def schedular2():
    conn, cur = connection()
    
    if request.method == "POST":
        conn, cur = connection()
        Notification = request.form["body"]
        Date = request.form["date"]
        Time = request.form["time"]
        QueueName = "Class_notification" 
        data={"ClassId":1,"StudentId":1,
               "StudentName":"Jyoti","Notification":Notification,
                "Date":Date,"Time":Time,"StudentEmail":"lllll"}
                #yyyy-mm-dd #09:00
        RBserver_sender(QueueName,data)
        
    return render_template("schedular2.html")



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000,debug=True)
   
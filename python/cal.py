#!/usr/bin/python3
import bisect
from icalendar import Event, Calendar
from datetime import timedelta, datetime, date, tzinfo
import calendar
import pytz
import locale

import pwd
import grp
import os

def normDT(dt):
    if type(dt) == date:
        dtmp = datetime.combine(dt, datetime.min.time())
        return pytz.utc.localize(dtmp,pytz.utc)
    return dt

def parseFile(g):
    ret = []
    gcal = Calendar.from_ical(g.read())
    for component in gcal.walk():
        
        # only want events
        if type(component) == Event:
            ret += [component]
            dtObject = normDT(component.get('dtstart').dt)

    # close file
    g.close()

    # make sure events are in order
    return sorted(ret,key=lambda x: normDT(x.get('dtstart').dt))

def selectTimeframe(events, timestamps, datetime1,datetime2=None):
    if not datetime2:
        datetime2 = datetime1 + (timedelta(days=1) - timedelta(seconds=1))

    start = bisect.bisect_left(timestamps, datetime1 )
    end   = bisect.bisect_right(timestamps, datetime2 )
    return events[start:end]
        
def dayPadding():
    return '<span class="jzdb"><!--BLANK--></span>\n'

def getTargetYearMonth(dt):
    return dt.strftime("%B, %Y")
def getMonthLink(dt):
    return dt.strftime("%Y&%-m.html")

def singleOverviewDay(year, month, numberOfDay, hasEvent):
    dayId = "day-{}".format(numberOfDay)
    if hasEvent:
        link = 'day-{}&{}&{}.html'.format(year,month,numberOfDay)
        html = '<a href={}> <span id="{}" class="circle">{}</span> </a>'.format(\
                        link, dayId, numberOfDay)
    else:
        html = '<span id="{}">{}</span>'.format(dayId, numberOfDay)
    return html

def createOverview(events, timestamps, firstDate):

    # preparation
    month   = firstDate.month
    weekday = firstDate.weekday() 
    
    # create padding at start
    padding = ''.join([dayPadding() for x in range(0,weekday)])
    
    # check which days will be highlighted
    exists = dict()
    for t in timestamps:
        if (not t.day in exists) and (t.month == month) and (t.year == firstDate.year):
                #print(events[timestamps.index(t)])
                #print(t)
                #print("---------------")
                exists.update({t.day:t.day})
    
    # create the actual content 
    content = padding

    daysOfMonths = calendar.monthrange(firstDate.year, firstDate.month)[1]
    for x in range(1, daysOfMonths+1):
        content += singleOverviewDay(firstDate.year, firstDate.month, x, x in exists)

    # create padding at end
    needed = (7 - (daysOfMonths + weekday)%7 )%7
    content += ''.join([dayPadding() for x in range(0, needed)])

    return content

def createSingleDayView(events, timestamps, day, cssDir, jsDir):

    # prepare colums
    completeLeft  = ""
    completeRight = ""

    # prepare templates
    leftItem  = '<div class="rectangle"> <p>{}</p> </div>'
    rightItem = '<div class="rectangle"> <p>{}</p> </div>'

    # find all relevant events
    selectedEvents = selectTimeframe(events, timestamps, datetime1=day)
    for event in selectedEvents:
        time = event.get('dtstart').dt
        if type(time) == date:
            leftPart = leftItem.format("All day")
        else:
            leftPart = leftItem.format(time.strftime("%H:%M"))
        
        location = event.get('LOCATION')
        hasDescription = event.get('DESCRIPTION')
        if not location:
            location = ""
        if hasDescription:
            description = '</br><a href={}.html>Details</a>'.format(event.get("UID"))
        else:
            description = ""
        buildDescription = "{}\n</br><i>{}</i>{}".format(\
                        event.get('SUMMARY'), location, description)
        rightPart = rightItem.format(buildDescription)
        
        # put it together
        completeLeft  += leftPart
        completeRight += rightPart

    # format base html
    return html_base_day.format(cssDir, jsDir, completeLeft,completeRight)
    
events = None
timestamps = None
def createBase(filename):
    global events
    global timestamps
    
    # set time output language
    try:
        locale.setlocale(locale.LC_TIME, "de_DE.utf8")
    except locale.Error:
        print("Cannot set custom locale, using system default.")

    #read in file
    events = parseFile(open(filename,'rb'))

    # simplify search as we wont change events
    timestamps = [ normDT(x.get('dtstart').dt) for x in events ]

def fixPermissions(fname, group):
    try:
        gid = grp.getgrnam(group).gr_gid
        os.chown(fname,uid=-1,gid=gid)
        os.chmod(fname,0o640)
    except PermissionError:
        pass

def buildAll(targetDir, cssDir, jsDir):
    global events
    global timestamps

    # build month views
    cur = datetime(timestamps[0].year,timestamps[0].month,1,tzinfo=pytz.utc)
    while cur <= timestamps[-1]:
        oneMonth = timedelta(days=calendar.monthrange(cur.year, cur.month)[1]);

        prevMonth = getMonthLink(cur-timedelta(days=1))
        curMonth  = getTargetYearMonth(cur)
        nextMonth = getMonthLink(cur+oneMonth)

        # build html
        html_full = html_base.format(
                         cssDir, \
                         jsDir,\
                         prevMonth,\
                         curMonth,\
                         nextMonth,\
                         createOverview(\
                              selectTimeframe(events, timestamps, cur, cur+oneMonth),\
                              selectTimeframe(timestamps,timestamps, cur, cur+oneMonth),
                              cur),\
                         )

        fname = "{}/month-{}&{}.html".format(targetDir,cur.year,cur.month)
        with open(fname,"w") as f:
            f.write(html_full)
        fixPermissions(fname, "www-data")
        cur += oneMonth;

    # build day views
    cur = datetime(timestamps[0].year,timestamps[0].month,timestamps[0].day,tzinfo=pytz.utc)
    while cur < timestamps[-1]:
        fname = "{}/day-{}&{}&{}.html".format(targetDir, cur.year,cur.month, cur.day)
        with open(fname,"w") as f:
            f.write(createSingleDayView(events, timestamps, cur, cssDir, jsDir))
        fixPermissions(fname, "www-data")
        cur += timedelta(days=1) 

    for e in events:
        uid = "{}/{}.html".format(targetDir, e.get("UID"))
        with open(uid,"w") as f:
            
            summary = e.get("SUMMARY")
            if not summary:
                summary = "Termin hat keinen Titel - meh"
            
            location    = e.get("LOCATION")
            if not location:
                location = "keine Angabe"
            
            description = e.get("DESCRIPTION")
            if description:
                description = description.replace("\n","\n</br>")

            content = '<b>{}</br></br></b><i>Ort: {}</br></br></i><hr></br><b>Beschreibung:</b></br>{}'
            content = content.format(summary,location,description)
            content = html_base_event.format(cssDir, jsDir, content)
            f.write(content)
        fixPermissions(uid, "www-data")

    # build detail views
    
    
html_base = '''
<!DOCTYPE html>
<html lang="en" >
  <head>
    <meta charset="UTF-8">
      <title>ATHQ</title>
      <link rel="stylesheet" href="{}/month.css">
      <script defer src="{}/site.js"></script>
  </head>
  <body>
    <div class="jzdbox1 jzdbasf jzdcal">
    <div class="headerbar">
        <div class="jzdcalt prev">
            <a class=prefNext href=month-{}>&laquo;</a>    
        </div>
        <div class="jzdcalt">{}</div>
        <div class="jzdcalt next">
            <a href=month-{}>&raquo;</a>
        </div>
    </div>
      <span>Mo</span>
      <span>Di</span>
      <span>Mi</span>
      <span>Do</span>
      <span>Fr</span>
      <span>Sa</span>
      <span>So</span>
      {}
    <div class="vspace">
        &nbsp; </br>
    </div>
    <div class="currentDate" id="time">
          Datum/Uhrzeit nicht verfügbar.
    </div>
    </div>
  </body>
</html>
'''

html_base_day = '''
<!DOCTYPE html>
<html lang="en" >
  <head>
    <meta charset="UTF-8">
    <title>ATHQ-single</title>
    <link rel="stylesheet" href="{}/day.css">
    <script defer src="{}/site.js"></script>
  </head>
  <body>
    <div class="row">
        <div class="column1">
            {}
        </div>
        <div class="column2">
            {}
        </div>
    </div>
  </body>
</html>
'''

html_base_event = '''
<!DOCTYPE html>
<html lang="en" >
  <head>
    <meta charset="UTF-8">
    <title>ATHQ-single</title>
    <link rel="stylesheet" href="{}/day.css">
    <script defer src="{}/site.js"></script>
  </head>
  <body>
      <div class="eventview">
            {}
      </div>
    </div>
  </body>
</html>
'''

import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AtlantisHQ CSS Calendar')
    parser.add_argument('icsFile', type=str, help='ics file to parse')
    parser.add_argument('targetDir', type=str, help='ics file to parse')
    parser.add_argument('cssDir', type=str, help='ics file to parse')
    parser.add_argument('jsDir', type=str, help='ics file to parse')
    args = parser.parse_args()
    createBase(args.icsFile)
    buildAll(args.targetDir,args.cssDir, args.jsDir)

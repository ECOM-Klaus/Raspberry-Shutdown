#!/usr/bin/env python3

# MIT License see https://opensource.org/licenses/MIT
# copyright (c) 2021 Klaus Mezger, ECOM Engineering
''' Simple python 3.x shutdown control using switch and LED

This script allows a controlled shutdown preventing SD-Card damage
Switch:
    press >3 seconds:  secure system shutdown is triggered
    double click:      secure shutdown and restart
    press >6 seconds:  optional supply shutdown with external hardware
LED:
    turns on, as soon as raspberry is ready
    turns off, as soon as controlled power down is compleded

For help use commandline "python3 s_shut.py -h"
For auto start call script from file /etc/rc.local:
    /home/pi/Projects/Shutdown/python3 s_shut.py &

Hardware component used:
    * 330Ohm resistor
    * Low current (green) LED
    * SPST switch 

Connections:
    * Raspi output port --> LED(anode)-LED(cathode) --> resistor --> GND
    * Raspi input Port --> switch --> GND
    * [optional, if not programmed in config.txt) Raspi input Port --> 10kOhm resistor to 3.3V]

Prerequisites, if using Raspberry internal pullup for switch:
    * Enable internal pullup on input port on bottom in file /boot/config.txt
        #set GPIO20 as input with pullup high
        gpio=20=ip,pu 
    
'''
import argparse

#key press time in sec
C_LONG = 3         #shutdown Raspberry off
C_SUPERLONG = 6    #shutdown & power off: needs external hardware


def getArgs():
    '''Read arguments from command line.'''

    ledDefault = 21
    switchDefault = 20
    powerDefault = 0

    parser = argparse.ArgumentParser()
                                        
    parser.add_argument("-l","--ledPort", type=int, default=ledDefault, metavar='',
                        help='LED output bcm port default = ' + str(ledDefault))
    parser.add_argument("-s", "--switchPort", type=int, default=switchDefault, metavar='',
                        help='Switch control input bcm port default = ' + str(switchDefault))
    parser.add_argument("-p", "--powerPort", type=int, default=powerDefault, metavar='',
                        help='Optional bcm port for external power timer')

    args=parser.parse_args()
    portHandler(args)

def portHandler(ports):
    '''Read switch, decode command, control LED feedback and execute command.''' 

    pwrString = ''
    if(ports.powerPort != 0):
        pwrString = 'Power: GPIO'+str(ports.powerPort)
        
    print('LED: GPIO'+str(ports.ledPort),
          'Switch: GPIO'+str(ports.switchPort),
          pwrString)

    chip = gpiod.Chip("0")
    inPort = chip.get_line(ports.switchPort)
    inPort.request("s_shut", type = gpiod.LINE_REQ_EV_BOTH_EDGES)

    LedPort = chip.get_line(ports.ledPort)
    LedPort.request("s_shut", type = gpiod.LINE_REQ_DIR_OUT)
    LedPort.set_value(1) #signal raspi is up

    if ports.powerPort > 0:
        powerPort = chip.get_line(ports.powerPort)
        powerPort.request("s_shut", type = gpiod.LINE_REQ_DIR_OUT)
        powerPort.set_value(0)

    keyAction = "NO_KEY"
    t_keyrelease = time.time()  

    pauseTime = 0.0
    pulseTime = 0.0
    blinkCount = int(0)
    checkDoublePress = False
#    event = inPort.event_read() #falling edge: key pressed
    
    while keyAction == "NO_KEY":
        try:
            keyAction == "NO_KEY"

#wait for key pressed
            event = inPort.event_read() #falling edge: key pressed
            print("type", event.type)
            if (event.type == 1): #dummy rising edge at power on or bounce
                print("first event should be falling --> ignore")
                continue #retry wait for falling edge

            t_keypress = event.sec + (event.nsec * 10e-10)
            pauseTime = t_keypress - t_keyrelease 

#wait for key released
            released = False
            #loop uses non-blocking timeout in order to toggle LED
            while released == False: 
                  released = inPort.event_wait(nsec=500000000) #0.5s
                  LedPort.set_value(blinkCount & int(1)) #toggle LED
                  blinkCount += 1
            LedPort.set_value(1) 
            event = inPort.event_read() #rising edge: key released
            print('timestamp: {}.{}'.format(event.sec, event.nsec))
            t_keyrelease = event.sec + (event.nsec * 10e-10)
            pulseTime = t_keyrelease - t_keypress

            if pulseTime < 0.01: # <10ms: debounce, forget key
                pulseTime = 0
            print("  pulse time =", pulseTime, "s"
                  "  pause time =", pauseTime)
               
 #analyze command
            #double click?
            if pulseTime < 0.5: 
                if checkDoublePress == False:
                    checkDoublePress = True
                    keyAction = "NO_KEY"
                else:
                    if pauseTime < 0.5: #this is a double click
                        keyAction = "DOUBLE_PRESS"
                        os.system("sudo shutdown -r now")
                        checkDoublePress = False
            else:          
                checkDoublePress = False
 
            if pulseTime > C_SUPERLONG:
                keyAction = "SUPER_LONG_PRESS"
                #power down needs power off through external circuitry
                powerPort.set_value(1) 
                os.system("sudo shutdown -P now")      

            elif pulseTime > C_LONG:
                keyAction = "LONG_PRESS"
                os.system("sudo shutdown -h now")

            print("keyAction =", keyAction)             
                         
        except KeyboardInterrupt:
            chip.close()
            break
 
    print("ciao")
 
if __name__ == "__main__":
    import gpiod
    import time
    import sys
    import os
    getArgs()




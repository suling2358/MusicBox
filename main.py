import machine
import utime
from machine import UART, Pin, Timer
from utime import sleep_ms, sleep
from picodfplayer import DFPlayer
from picodfplayer import VolSet, WriteVol, ReadVol
from mfrc522 import MFRC522
from array import *
from ir_rx.nec import NEC_16
from ir_rx.print_error import print_error
from micropython import const
from ota import OTAUpdater
from DspPattern import Pattern
from globvars import *
from fnKeys import *

Release = const(5)
TestOne = False
TestTwo = False

###################################################################
# IR remote for control commands - Vzio Remote
###################################################################
VZVOLUP  = const(0x02)
VZVOLDN  = const(0x03)
VZINPUT  = const(0x2F)
VZEXIT   = const(0x49)
VZAMZN   = const(0xEA)
VZNFLX   = const(0XEB)
VZMGO    = const(0xED)
VZRED    = const(0x54)
VZYELLOW = const(0x52)
VZBLUE   = const(0x53)
VZGREEN  = const(0x55)

###################################################################
# IR remote for control commands - BLS Light
###################################################################
BLVOLUP   = const(0x09)
BLVOLDN   = const(0x07)
BLCOOL    = const(0x42)
BLNATURAL = const(0x52)
BLWARM    = const(0x4A)




################################################################
# different versions have different pin assignments
################################################################
if (Version == 4):
    Irs = 8
    FolderList = [1,2,4,3]       # switching green and yellow lights
else:
    Irs = 5
    FolderList = [1,2,3,4]


Ser0 = Pin(SER0, Pin.OUT)
Ser1 = Pin(SER1, Pin.OUT)
Ser2 = Pin(SER2, Pin.OUT)
Ser3 = Pin(SER3, Pin.OUT)
Srclk = Pin(SRCLK, Pin.OUT)
Rclk = Pin(RCLK, Pin.OUT)

LData0 = 0xAA
LData1 = 0xAA
LData2 = 0xAA
LData3 = 0xBB

Srclk.value(0)
Rclk.value(1)

PatMax  = len(Pattern)
PatNext = 0
PatCnt  = 0
PatChg  = 1

####################################################################
# Pre-defined Subroutines
####################################################################

####################################################################
# IR callback routine
####################################################################
def ir_callback(data, addr, ctrl):
    global ir_data
    global ir_addr
    if data > 0:
        ir_data = data
        ir_addr = addr

####################################################################
# DFPlayer routines
####################################################################
####################################################################
# PlayPlayList: starts playing the a list of tracks
####################################################################
def PlayPlayList(pidx):
    global PlayList
    global PListCurr
    global TrackCurr
    global ModeCurr
    global VolCurr
    global PlayMode
    global BtnArr
    global BtnOn
    
    if (pidx >= len(PlayList)):
        return
    
    PListCurr = pidx
    TrackCurr = 0
    tfolder = PlayList[PListCurr][TrackCurr][0]
    ttrack  = PlayList[PListCurr][TrackCurr][1]
    
    player.setVolume(VolCurr)
    player.playTrack(tfolder, ttrack)
    print(f"playing {tfolder},{ttrack}")
    BtnLedOff(BtnArr)
    
    BtnOn = tfolder - 1
    
    PlayMode = LISTS
    return

####################################################################
# NextPlayList: play the next track in the list
####################################################################
def NextPlayList():
    global PlayList
    global PListCurr
    global TrackCurr
    global PlayMode
    global ListLen
    global LockCnt
    global BtnOn
        
    LockCnt = 0
    TrackCurr = TrackCurr + 1
    # check to seeif we are at the end of the list
    if (TrackCurr >= ListLen):
        PlistCurr = -1
        TrackCurr = 0
        PlayMode  = IDLE
        BtnOn = 99
        BtnLedOff()
        return
    else:
        tfolder = PlayList[PListCurr][TrackCurr][0]
        ttrack  = PlayList[PListCurr][TrackCurr][1]
        print(f"playing {tfolder}, {ttrack} {LockCnt}")
        player.setVolume(VolCurr)
        player.playTrack(tfolder, ttrack)
        LockCnt = 0
        return

####################################################################
# PlaySingleTrack: play just one track from a folder
####################################################################
def PlaySingleTrack(fidx,tidx):
    global PListCurr
    global TrackCurr
    global ModeCurr
    global PlayMode
    global VolCurr
    global BtnOn
    global BtnArr   

    PListCurr = 0
    TrackCurr = tidx
    tfolder   = fidx
    ttrack    = tidx
    print(f"playing {tfolder}, {ttrack}")
    
    player.setVolume(VolCurr)
    player.playTrack(tfolder, ttrack)
    
    # turn on one of the four LED under the keys
    BtnLedOff(BtnArr)
    BtnOn = (tfolder-1) % 4
            
    PlayMode = SINGLE
    return

################################################################
#LED Display Routine
################################################################
#Push out one byte
def DspByte(idx):
    global Pattern
    global Ser0
    global Ser1
    global Ser2
    global Ser3
    global Srclk
    global Rclk
    
    lc0 = Pattern[idx][0]
    lc1 = Pattern[idx][1]
    lc2 = Pattern[idx][2]
    lc3 = Pattern[idx][3]
    #print(idx,lc0,lc1,lc2,lc3)

    for i in range(8):
        #and out last bit
        Ser0.value(lc0 & 0x1)
        Ser1.value(lc1 & 0x1)
        Ser2.value(lc2 & 0x1)
        Ser3.value(lc3 & 0x1)
        #clock in this bit
        Srclk.value(1)
        utime.sleep_us(2)
        Srclk.value(0)
        lc0 = lc0 >> 1
        lc1 = lc1 >> 1
        lc2 = lc2 >> 1
        lc3 = lc3 >> 1

    #Done shifting, display output        
    Rclk.value(1)
    utime.sleep_us(2)
    Rclk.value(0)   
            
#Display pattern
def DspPattern():
    global LData0
    global LData1
    global LData2
    global LData3
    global Pattern
    
    for i in range(MaxPat):
        DspByte(i)
        #sleep(4)
    return

    

################################################################
# Check if new card present
# if yes read
################################################################        
def CheckTag():
    global player
    global TagPrvCard
    global TagVal1
    global TagVal2
    
    reader.init()    
    (stat, tag_type) = reader.request(reader.REQIDL)
    if stat == reader.OK:
        #tag present        player.playTrack(retcd,TrackCurr)
        (stat, uid) = reader.SelectTagSN()
        if uid == TagPrvCard:
            #return if it is the same card as before
            return 0
            
        if stat == reader.OK:
            #different tag
            print("Card detected {}  uid={}".format(hex(int.from_bytes(bytes(uid),"little",False)).upper(),reader.tohexstring(uid)))
            TagPrvCard = uid
            
            if reader.IsNTAG():
                #print("Got NTAG{}".format(reader.NTAG))
                #reader.MFRC522_Dump_NTAG(Start=0,End=reader.NTAG_MaxPage)
                return 0
            else:
                (stat, tag_type) = reader.request(reader.REQIDL)
                if stat == reader.OK:
                   (stat, uid2) = reader.SelectTagSN()
                   if stat == reader.OK:
                       if uid != uid2:
                           return 0
                       defaultKey = [255,255,255,255,255,255]
  #
                       absoluteBlock = 8
                       keyA=defaultKey
                       status = reader.authKeys(uid,absoluteBlock,keyA)
                       if status == reader.OK:
                           status, block1 = reader.read(absoluteBlock)
                           absoluteBlock = 9
                           status, block2 = reader.read(absoluteBlock)                    
                           for i in range(16):
                               TagVal1[i] = block1[i]
                               TagVal2[i] = block2[i]
                           print(TagVal1)
                           print(TagVal2)
                           return 1
                       else:
                           print("auth failed")            
    
    return 0



####################################################################
# Timer Callback
####################################################################         
#def timer_callback(timer):
def timer_callback():
    global player
    global PatNext
    global PatMax
    global PatCnt
    global PatChg
    global TagPrvCard
    global TagVal
    global LockCnt
    global SEC3
    global MIN30
    global SETVOL
    global VolCurr
    global LISTS
    global ir_data
    global PlayMode
    global ListLen
    global InActivity
    global SSID
    global PASSWORD
    global Btn
    global BtnOn
    global BtnIrqFlag
    
    ##########################################################
    # track inactivity; after 30 minutes turn OFF most lights
    ##########################################################
    if (LockCnt > ACTTHR) and (PlayMode == IDLE):
        InActivity = True
        #print("sleep")
    else:
        InActivity = False

    # Display next pattern
    # interrupts happen faster then display changes
    # PatCnt counts up until the display should be changed
    PatCnt = PatCnt + 1
    if (InActivity == False):     
        if (PatCnt > PatChg): 
            PatCnt = 0
            PatNext = PatNext + 1
            if (PatNext >= PatMax):
                PatNext = 0
            DspByte(PatNext)
        if (BtnOn < 5):
            BtnArr[BtnOn].toggle()
            
    else:
        DspByte(0)
        

    ################################################################
    # Lock out period
    # no new selection will be processed during this period
    ################################################################
    LockCnt = LockCnt + 1
    if (LockCnt < SEC3):
        return
    TagPrvCard = [0]
               
    ################################################################
    # check to see if RFID tag has been read
    ################################################################
    retidx = CheckTag()
    if (retidx == 1):
        tagcmd = TagVal1[0]
        if (tagcmd == SETVOL):
            volume = TagVal1[2]
            if (volume >=0) and (volume <= 30):
                VolCurr = volume
                VolSet(player, VolCurr)
                LockCnt = 0
            return
        
        ###############################################################
        # predefined lists
        ###############################################################
        elif (tagcmd == LISTS):
            print(f"pre-defined list {TagVal1[1]}")
            plen = len(PlayList)
            if (TagVal1[1] >= plen):
                return
            nnfolder = FolderList[TagVal1[1]-1]
            ListLen = len(PlayList[nnfolder])
            PlayPlayList(nnfolder)
            print(f"playfolder {TagVal1[1]},. {nnfolder}")

            LockCnt = 0
            return
        
        ###############################################################
        # dynamic list, built from tag
        # list built in PlayList[0]
        ###############################################################           
        elif (tagcmd == TRACKS):
            nn = TagVal1[1]
            print(f"Dynamic List {nn}")
            
            PlayList[0] = []
            j = 2
            for i in range(nn):
                PlayList[0].append([TagVal1[j],TagVal1[j+1]])
                j = j + 2
            print(PlayList[0])
            ListLen = len(PlayList[0])
            PlayPlayList(0)
            return
        
        ###############################################################
        # Test, Update
        ###############################################################           
        elif (tagcmd == UPDATE):        
            nn = TagVal1[1]
            tssid = ""
            for i in range(nn):
                tssid = tssid + chr(TagVal1[i+2])
            nn = TagVal2[1]
            tpass = ""
            for i in range(nn):
                tpass = tpass + chr(TagVal2[i+2])
            SSID = tssid
            PASSWORD = tpass
            BtnLedOn(BtnArr)
            firmware_url = "https://raw.githubusercontent.com/suling2358/MusicBox/refs/heads/"
            ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
            ota_updater.download_and_install_update_if_available()
            BtnFlash(BtnArr, 5)
            LockCnt = 0
            return        
        return    
            
    ###############################################################
    # section for processing the buttons
    ###############################################################
    for i in range(4):
        if (BtnIrqFlag[i] == 1):
            player.playTrack(5, 1)
            utime.sleep_ms(100)
            ListLen = len(PlayList[i+1])
            PlayPlayList(i+1)
            BtnIrqFlag[i] = 2
            LockCnt = 0
            BtnLedOff(BtnArr)
            BtnOn   = i
            print(f"playing {(i+1)}")
        
        elif (BtnIrqFlag[i] == 2) and (BtnLockCnt[i] > 4): 
            BtnLedOneOff(i)
            BtnIrqFlag[i] = 0    
            Btn[i].irq(trigger=machine.Pin.IRQ_RISING, handler=BtnIntp[i])       
        BtnLockCnt[i] = BtnLockCnt[i] + 1
         
    
    ###################################################################
    # check IR remote for control commands
    ###################################################################
    if ir_data > 0:
        print('Data {:02x} Addr {:04x}'.format(ir_data, ir_addr))
                                                    # Vol +
        if (ir_data == VZVOLUP) or (ir_data == BLVOLUP):               
            VolCurr = VolCurr + 1
            VolSet(player, VolCurr)
                                                    # Vol -
        elif (ir_data == VZVOLDN) or (ir_data == BLVOLDN):  
            VolCurr = VolCurr - 1
            VolSet(player, VolCurr)
        elif (ir_data == VZINPUT):
            PlaySingleTrack(1,1)                     # Input Key
            LockCnt = 0
        elif (ir_data == VZEXIT):
            PlaySingleTrack(2,5)                     # Exit Key
            LockCnt = 0
        elif (ir_data == VZAMZN):
            PlaySingleTrack(2,1)                     # Amazon
            LockCnt = 0
        elif (ir_data == VZNFLX):
            PlaySingleTrack(2,2)                     # Netflix
            LockCnt = 0
        elif (ir_data == VZMGO):
            PlaySingleTrack(2,5)                     # MGO
            LockCnt = 0
        elif (ir_data == VZRED):
            j = FolderList[1-1]
            ListLen = len(PlayList[j])               # Red button
            PlayPlayList(j)
            LockCnt = 0
        elif (ir_data == VZYELLOW) or (ir_data == BLNATURAL):
            PlaySingleTrack(3,10) 
            LockCnt = 0
        elif (ir_data == VZGREEN):
            j = FolderList[4-1]
            ListLen = len(PlayList[j])               
            PlayPlayList(j)
            LockCnt = 0
        elif (ir_data == VZBLUE):
            j = FolderList[2-1]
            ListLen = len(PlayList[j])               
            PlayPlayList(j)
            LockCnt = 0 
        else:
            pn = len(PlayList) -  1
            j  = (ir_data % pn) + 1

            ListLen = len(PlayList[j])
            PlayPlayList(j)
            print(f"playlist {j},len {ListLen}")
            LockCnt = 0
            
        ir_data = 0
        return
    
    
    ###################################################################
    # End of the Timer Loop
    # check to see if we need to continue playing to next track
    # only if the player is not busy
    ###################################################################
    if (PlayMode == LISTS):
        #already playing a list, wait for not busy
        if (HwdBusyPin.value() == 0): 
            return
        else:
            print("Next")
            # ready for next file in list        
            NextPlayList()      
            return    
    elif (PlayMode == SINGLE):
        #already playing a list, wait for not busy
        if (HwdBusyPin.value() == 0): 
            return
        else:
            # done playing single track
            PlayMode = IDLE
            BtnLedOff(BtnArr)
            BtnOn = 99
    
            return       
#end of timer_callback

####################################################################
# End of Subroutine Section
####################################################################

####################################################################
# DFPlayer Mini Section
####################################################################
UART_INSTANCE=0
TX_PIN   = 16
RX_PIN   = 17
BUSY_PIN = 9
HwdBusyPin=Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)

#PlayList defs [folder, track] format
PlayList = [[[1,1]],                                                                                           #not used
            [[1,1],[1,2],[1,3],[1,4],[1,5],[1,6],[1,7],[1,8],[1,9],[1,10],[1,11],[1,12]],                      #playlist 1
            [[2,1],[2,2],[2,3],[2,4],[2,5],[2,6],[2,7],[2,8],[2,9],[2,10],[2,11],[2,12],[2,13],[2,14],[2,15],[2,16],
             [2,17],[2,18],[2,19],[2,20],[2,21]],                                                              #         2
            [[3,1],[3,2],[3,3],[3,4],[3,5],[3,6],[3,7],[3,8],[3,9],[3,10],[3,11],[3,12],[3,13],[3,14],[3,15],
              [3,17],[3,18],[3,19],[3,20],[3,21],[3,22]],                                                      #         3
            [[4,1],[4,2],[4,3]]                                                                                #         4
           ]

TrackCurr  = 1
FolderCurr = 1
PListCurr  = 0
IDLE       = 0
PlayMode   = IDLE
ListLen    = 0
ListCnt    = 0

# now actually create the instance, reset and read stored volume data
player=DFPlayer(UART_INSTANCE, TX_PIN, RX_PIN, BUSY_PIN)
player.reset()
VolCurr = ReadVol()
print(f"read {VolCurr}")

# setup IR Remote callback
#ir = NEC_16(Pin(5, Pin.IN), ir_callback)
ir_data = 0
ir_addr = 0
ir = NEC_16(Pin(Irs, Pin.IN), ir_callback)

    
######################################################################
# RFID MFRC522 reader
######################################################################  
reader = MFRC522(spi_id=0,sck=2,miso=4,mosi=3,cs=1,rst=0)
TagPrvCard = [0]
TagCmd     = 0
TagVal1    = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]
TagVal2    = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]
TagCnt     = 0

######################################################################
# timer stuff section
######################################################################
TICPD      = 400                  # hand calculate all these to keep integer
SEC1       = 3        
SEC2       = 5
SEC3       = 8
SEC4       = 10
SEC5       = 13
ACTTHR     = 4500                 # 30 minutes at current TICPD
InActivity = False
LockCnt    = 0
TicLast    = 0
TicCurr    = 0


TicLast = utime.ticks_ms()
#Tic = Timer(period=TICPD, mode=Timer.PERIODIC, callback=timer_callback)
BtnRelease(BtnArr, Release)
sleep(3)
BtnLedOff(BtnArr)
print("Go");

######################################################################
# code loop
######################################################################
while True:
    timer_callback()
    TicCurr = utime.ticks_ms()
    nndif = utime.ticks_diff(TicCurr, TicLast)
    while (nndif < TICPD):
        TicCurr = utime.ticks_ms()
        nndif = utime.ticks_diff(TicCurr, TicLast)
    TicLast = TicCurr



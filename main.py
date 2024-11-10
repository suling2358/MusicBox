# More details can be found in TechToTinker.blogspot.com 
# George Bantique | tech.to.tinker@gmail.com
import machine
import utime
from machine import UART, Pin, Timer
from utime import sleep_ms, sleep
from picodfplayer import DFPlayer
from mfrc522 import MFRC522
from array import *
from ir_rx.nec import NEC_16
from ir_rx.print_error import print_error
from micropython import const
from WifiConfig import SSID, PASSWORD

print(f"{SSID}, {PASSWORD}")

Version = 4
TestOne = True
TestTwo = False

################################################################
# different versions have different pin assignments
################################################################
if (Version == 4):
    Irs = 8
    FolderList = [1,2,4,3]       # switching green and yellow lights
else:
    Irs = 5
    FolderList = [1,2,3,4]

# RFID commands for the MusicBox
# two bytes at block 8
# 1st byte: cmd
SETVOL     = const(1)            # set volume
FOLDERS    = const(2)            # play folder (no longer used)
LISTS      = const(3)            # play list
TRACKS     = const(4)            # dynamic list (tracks defined in the tag)
SINGLE     = const(5)
TEST       = const(99)

# 2nd byte for set volume
MUTETAG    = const(10)
LOWTAG     = const(11)
NOMTAG     = const(12)
HIGHTAG    = const(13)
LOUDTAG    = const(14)
VOLMUTE    = const(0)
VOLLOW     = const(11)
VOLNOM     = const(18)
VOLHIGH    = const(25)
VOLLOUD    = const(30)
VolCurr    = VOLNOM

#LED constants and variables
#LED displays using HC595
SER0     = 21
SER1     = 20
SER2     = 19
SER3     = 18
SRCLK    = 22
RCLK     = 26

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

Pattern    = [
    [0x00, 0x00, 0x00, 0x00],
    [0xAA, 0xAA, 0xAA, 0xAA],
    [0x55, 0x55, 0x55, 0x55],
    [0x55, 0xAA, 0x55, 0xAA],
    [0xAA, 0x55, 0xAA, 0x55],
    [0xAA, 0x00, 0x55, 0x00],
    [0x44, 0x44, 0x44, 0x44],
    [0xFF, 0x00, 0xFF, 0x00],
    [0x00, 0x55, 0x00, 0xAA],
    [0xFF, 0xFF, 0xFF, 0xFF]
]
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
        #print('Data {:02x} Addr {:04x}'.format(data, addr))

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
    global PlayMode
    
    if (pidx >= len(PlayList)):
        return
    
    PListCurr = pidx
    TrackCurr = 0
    tfolder = PlayList[PListCurr][TrackCurr][0]
    ttrack  = PlayList[PListCurr][TrackCurr][1]
    
    player.setVolume(VolCurr)
    player.playTrack(tfolder, ttrack)
    print(f"playing {tfolder},{ttrack}")
    
    # turn on one of the four LED under the keys
    BtnLedOne(tfolder)
    
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
        
    LockCnt = 0
    TrackCurr = TrackCurr + 1
    # check to seeif we are at the end of the list
    if (TrackCurr >= ListLen):
        PlistCurr = -1
        TrackCurr = 0
        PlayMode  = IDLE
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
    

    PListCurr = 0
    TrackCurr = tidx
    tfolder   = fidx
    ttrack    = tidx
    print(f"playing {tfolder}, {ttrack}")
    
    player.setVolume(VolCurr)
    player.playTrack(tfolder, ttrack)
    
    # turn on one of the four LED under the keys
    BtnLedOne(tfolder)
    
    PlayMode = SINGLE
    return

####################################################################
# Volume control Section
# VolSet: sets the volume
# read and write volume data saved in NVRAM
####################################################################
def VolSet(volidx):
    global player
    
    if (volidx > 30):
        i = 30
    elif (volidx < 0):
        i = 0
    else:
        i= volidx
    player.setVolume(i)
    print(f"setting vol to {i}")
    WriteVol()
    

def ReadVol():
    global VolCurr
    
    try:
        configFile=open('volume','r')
        vol=eval(configFile.read())
        configFile.close()
    except:
        vol = VOLNOM
        
    VolCurr = vol
    print(f"Volume {VolCurr}")

def WriteVol():
    global VolCurr
    
    configFile=open('volume','w')
    configFile.write(repr(VolCurr))
    configFile.close()

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
# turn off all button leds
################################################################
def BtnLedOff():
    for i in range(4):
        BtnArr[i].value(0)

################################################################
# turn one LED on
################################################################
def BtnLedOne(idx):
    BtnLedOff()
    j = (idx-1) % 4
    BtnOn     = j
    BtnOnFlip = 1
    BtnArr[BtnOn].value(BtnOnFlip)

################################################################
# Check if new card present
# if yes read
################################################################        
def CheckTag():
    global TagPrvCard
    global TagVal
    
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
                       #reader.MFRC522_DumpClassic1K(uid,Start=0, End=64, keyA=defaultKey)
                       #reader.MFRC522_DumpClassic1K(uid,Start=8, End=10, keyA=defaultKey)
                       absoluteBlock = 8
                       keyA=defaultKey
                       status = reader.authKeys(uid,absoluteBlock,keyA)
                       if status == reader.OK:
                           status, block = reader.read(absoluteBlock)
                           #print(f"block {block[0]}")
                           # This is good for 26 folders (A-Z)
                           for i in range(16):
                               TagVal[i] = block[i]
                           print(f"Tag {TagVal[0]},{TagVal[1], TagVal[2]}")
                           return 1
                       else:
                           print("auth failed")            
    
    return 0



####################################################################
# Timer Callback
####################################################################         
#def timer_callback(timer):
def timer_callback():
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
            BtnOnFlip = (BtnOnFlip + 1) % 2
            BtnArr[BtnOn].value(BtnOnFlip)
            
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
        tagcmd = TagVal[0]
        if (tagcmd == SETVOL):
            tagval = TagVal[1]
            if (tagval == MUTETAG):
                VolCurr = VOLMUTE
            elif (tagval == LOWTAG):
                VolCurr = VOLLOW
            elif (tagval == NOMTAG):
                VolCurr = VOLNOM
            elif (tagval == HIGHTAG):
                VolCurr = VOLHIGH
            elif (tagval == LOUDTAG):
                VolCurr = VOLLOUD
            VolSet(VolCurr)
            LockCnt = 0
            return
        
        ###############################################################
        # predefined lists
        ###############################################################
        elif (tagcmd == LISTS):
            print(f"pre-defined list {TagVal[1]}")
            plen = len(PlayList)
            if (TagVal[1] >= plen):
                return
            nnfolder = FolderList[TagVal[1]-1]
            ListLen = len(PlayList[nnfolder])
            PlayPlayList(nnfolder)
            print(f"playfolder {TagVal[1]},. {nnfolder}")
            LockCnt = 0
            return
        
        ###############################################################
        # dynamic list, built from tag
        # list built in PlayList[0]
        ###############################################################           
        elif (tagcmd == TRACKS):
            nn = TagVal[1]
            print(f"Dynamic List {nn}")
            
            PlayList[0] = []
            j = 2
            for i in range(nn):
                PlayList[0].append([TagVal[j],TagVal[j+1]])
                j = j + 2
            print(PlayList[0])
            ListLen = len(PlayList[0])
            PlayPlayList(0)
            return
        return    
            
    ###############################################################
    # section for processing the buttons
    ###############################################################
    BtnState[1] = Btn1.value()   
    BtnState[2] = Btn2.value()   
    BtnState[3] = Btn3.value()
    BtnState[4] = Btn4.value()

    
    # now see if any of the buttons has been pressed
    if (BtnState[1] == 0):
        ListLen = len(PlayList[1])
        PlayPlayList(1)
        LockCnt = 0
        return
    elif (BtnState[2] == 0):
        ListLen = len(PlayList[2])
        PlayPlayList(2)
        LockCnt = 0
        return
    elif (BtnState[3] == 0):
        ListLen = len(PlayList[3])
        PlayPlayList(3)
        LockCnt = 0
        return
    elif (BtnState[4] == 0):
        ListLen = len(PlayList[4])
        PlayPlayList(4)
        return        
    
    ###################################################################
    # check IR remote for control commands
    ###################################################################
    RMVOLUP = const(0x02)
    RMVOLDN = const(0x03)
    RMINPUT = const(0x2F)
    RMEXIT  = const(0x49)
    RMAMZN  = const(0xEA)
    RMNFLX  = const(0XEB)
    RMMGO   = const(0xED)
    RMRED   = const(0x54)
    RMYELLOW = const(0x52)
    RMBLUE  = const(0x53)
    RMGREEN = const(0x55)
    if ir_data > 0:
        print('Data {:02x} Addr {:04x}'.format(ir_data, ir_addr))
        if (ir_data == RMVOLUP):                     # Vol+
            VolCurr = VolCurr + 1
            VolSet(VolCurr)
        elif (ir_data == RMVOLDN):                   # Vol-
            VolCurr = VolCurr - 1
            VolSet(VolCurr)
        elif (ir_data == RMINPUT):
            PlaySingleTrack(1,1)                     # Input Key
            LockCnt = 0
        elif (ir_data == RMEXIT):
            PlaySingleTrack(2,5)                     # Exit Key
            LockCnt = 0
        elif (ir_data == RMAMZN):
            PlaySingleTrack(2,1)                     # Amazon
            LockCnt = 0
        elif (ir_data == RMNFLX):
            PlaySingleTrack(2,2)                     # Netflix
            LockCnt = 0
        elif (ir_data == RMMGO):
            PlaySingleTrack(2,5)                     # MGO
            LockCnt = 0
        elif (ir_data == RMRED):
            j = FolderList[1-1]
            ListLen = len(PlayList[j])               # Red button
            PlayPlayList(j)
            LockCnt = 0
        elif (ir_data == RMYELLOW):
            j = FolderList[3-1]
            ListLen = len(PlayList[j])               
            PlayPlayList(j)
            print(f"yellow {j}")
            LockCnt = 0
        elif (ir_data == RMGREEN):
            j = FolderList[4-1]
            ListLen = len(PlayList[j])               
            PlayPlayList(j)
            LockCnt = 0
        elif (ir_data == RMBLUE):
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
            BtnLedOff()

            print("single")
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
sleep(2)
ReadVol()

# setup IR Remote callback
#ir = NEC_16(Pin(5, Pin.IN), ir_callback)
ir_data = 0
ir_addr = 0
ir = NEC_16(Pin(Irs, Pin.IN), ir_callback)

######################################################################
# Keys and Key Led
######################################################################
BTN1     = 10
BTN2     = 11
BTN3     = 12
BTN4     = 13
BTNLED1  = 6
BTNLED2  = 7
BTNLED3  = 14
BTNLED4  = 15
Btn1 = Pin(BTN1, Pin.IN, Pin.PULL_UP)
Btn2 = Pin(BTN2, Pin.IN, Pin.PULL_UP)
Btn3 = Pin(BTN3, Pin.IN, Pin.PULL_UP)
Btn4 = Pin(BTN4, Pin.IN, Pin.PULL_UP)
BtnLed1  = Pin(BTNLED1, Pin.OUT)
BtnLed2  = Pin(BTNLED2, Pin.OUT)
BtnLed3  = Pin(BTNLED3, Pin.OUT)
BtnLed4  = Pin(BTNLED4, Pin.OUT)
BtnArr   = [BtnLed1, BtnLed2, BtnLed3, BtnLed4]
BtnOn    = 99
BtnOnFlip = 0
BtnState = [0,1,1,1,1]

# init key LED to OFF
BtnLedOff()
    
######################################################################
# RFID MFRC522 reader
######################################################################  
reader = MFRC522(spi_id=0,sck=2,miso=4,mosi=3,cs=1,rst=0)
TagPrvCard = [0]
TagCmd     = 0
TagVal     = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
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

print("Go")
TicLast = utime.ticks_ms()
#Tic = Timer(period=TICPD, mode=Timer.PERIODIC, callback=timer_callback)

######################################################################
# TestOne: Led under the switch
######################################################################
if (TestOne == True):
    while True:
        BtnLedOff()
        sleep(2)
        for i in range(4):
            BtnArr[i].value(1)
            sleep(1)
        sleep(1)

######################################################################
# TestTwo: Connect with DFPlayer
######################################################################
if (TestTwo == True):
    player.playTrack(1, 1)
    while True:
        sleep(1)



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


import machine
import utime
from machine import UART, Pin, Timer
from utime import sleep_ms, sleep
from picodfplayer import DFPlayer
from picodfplayer import VolSet, WriteVol, ReadVol
from mfrc522 import MFRC522
from array import *
#from ir_rx.nec import NEC_16
from ir_rx.sony import SONY_20
from ir_rx.print_error import print_error
from micropython import const
from ota import OTAUpdater
from DspPattern import *
from globvars import *
from fnKeys import *

Release = const(13)
TestOne = False
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
# PlayPlayFolder: play all tracks in a folder
####################################################################
def PlayPlayFolder(pidx):
    global FolderCurr
    global TrackCurr
    global VolCurr
    global PlayMode
    global BtnArr
    global BtnOn
    
    if (pidx > 4):
        return
    
    FolderCurr  = pidx
    TrackCurr   = 1
    tfolder     = FolderCurr
    ttrack      = TrackCurr
    
    player.setVolume(VolCurr)
    player.playTrack(tfolder, ttrack)
    print(f"playing {tfolder},{ttrack}")
    BtnLedOff(BtnArr)
    
    BtnOn = tfolder - 1
    
    PlayMode = FOLDERS
    return


####################################################################
# PlayPlayList: starts playing the a list of tracks
####################################################################
def PlayPlayList(pidx):
    global PlayList
    global PListCurr
    global TrackCurr
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
    print(f"next len {ListLen}, track {TrackCurr}")
    # check to seeif we are at the end of the list
    if (TrackCurr >= ListLen):
        PlistCurr = -1
        TrackCurr = 0
        PlayMode  = IDLE
        BtnOn = 99
        BtnLedOff(BtnArr)
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
# NextPlayFolder: play the next track in the folder
####################################################################
def NextPlayFolder():
    global FolderCurr
    global TrackCurr
    global PlayMode
    global LockCnt
    global BtnOn
        
    # try to play next track in folder
    LockCnt = 0
    TrackCurr = TrackCurr + 1
    tfolder   = FolderCurr
    ttrack    = TrackCurr
    player.setVolume(VolCurr)
    player.playTrack(tfolder, ttrack)
    print(f"next in folder {ttrack}")
    utime.sleep_ms(1)
    # test if busy
    if (HwdBusyPin.value() == 0):        # yes, busy
        LockCnt = 0
        return
    else:                                # not busy, done playing folder
        print("folder done")
        FolderCurr = -1
        TrackCurr = 0
        PlayMode  = IDLE
        BtnOn = 99
        BtnLedOff(BtnArr)
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
    global player

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
  
def PlayBeep():
    global player
    
    player.playTrack(5, 1)
    utime.sleep_ms(100)

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
    global FirstFlag
    
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
    if (InActivity == False) and (FirstFlag == False):     
        if (PatCnt > PatChg): 
            PatCnt = 0
            PatNext = PatNext + 1
            if (PatNext >= PatMax):
                PatNext = 0
            DspByte(PatNext)
        if (BtnOn < 5):
            BtnArr[BtnOn].toggle()
            
    elif (FirstFlag == False):
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
            PlayBeep()
            j = i + 1
            PlayPlayFolder(j)
            BtnIrqFlag[i] = 2
            LockCnt = 0
            BtnLedOff(BtnArr)
            BtnOn   = i
            print(f"playing folder {j}")
        
        elif (BtnIrqFlag[i] == 2) and (BtnLockCnt[i] > 4): 
            BtnLedOneOff(i)
            BtnIrqFlag[i] = 0    
            Btn[i].irq(trigger=machine.Pin.IRQ_RISING, handler=BtnIntp[i])
            if (FirstFlag == True):
                FirstFlag = False
                PlayBeep()
                utime.sleep_ms(100)
                PlayBeep()
                
        BtnLockCnt[i] = BtnLockCnt[i] + 1
         
    
    ###################################################################
    # check IR remote for control commands
    ###################################################################
    if ir_data > 0:
        print('Data {:02x} Addr {:04x}'.format(ir_data, ir_addr))
        dictdata = SonyRemote.get(ir_data)
        if (dictdata):
            print(f"dictdata {dictdata[0]}, {dictdata[1]}")
            if (dictdata[0] == 99):                     # Volume Special Case
                if (dictdata[1] == 1):
                    VolCurr = VolCurr + 1               # Vol-
                    VolSet(player, VolCurr)   
                elif (dictdata[1] == 2):
                    VolCurr = VolCurr - 1               # Vol+
                    VolSet(player, VolCurr)
                elif (dictdata[1] == 3):
                    VolCurr = 0                         # Mute
                    VolSet(player, VolCurr)    
            else:
                tfolder = dictdata[0]
                ttrack  = dictdata[1]
                PlaySingleTrack(tfolder,ttrack)                     
                LockCnt = 0
        else:
            print("dict not found")
        ir_data = 0
        return
    
    
    ###################################################################
    # End of the Timer Loop
    # check to see if we need to continue playing to next track
    # only if the player is not busy
    ###################################################################
    
    # still busy
    if (HwdBusyPin.value() == 0): 
        return
    if (PlayMode == LISTS):
        print("Next on List")     
        NextPlayList()      
        return
    elif (PlayMode == FOLDERS):
        NextPlayFolder()      
        return
        
    elif (PlayMode == SINGLE):
        # done playing single track, reset for Idle
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
PlayList = [[[1,1]],                                                                #not used
            [[1,1], [1,2], [1,3], [1,4], [1,5], [1,6], [1,7], [1,8], [1,9],[1,10],
             [1,11],[1,12]],                                                        #playlist 1
            [[2,1], [2,2], [2,3], [2,4], [2,5], [2,6], [2,7], [2,8], [2,9], [2,10],
             [2,11],[2,12],[2,13],[2,14],[2,15],[2,16],[2,17],[2,18],[2,19],[2,20],
             [2,21]],                                                               #         2
            [[3,1], [3,2], [3,3], [3,4], [3,5], [3,6], [3,7], [3,8], [3,9], [3,10],
             [3,11],[3,12],[3,13],[3,14],[3,15],[3,16],[3,17],[3,18],[3,19],[3,20],
             [3,21],[3,22],[3,23]],                                                 #         3
            [[4,1], [4,2], [4,3], [4,4], [4,5], [4,6], [4,7], [5,8], [4,9], [4,10],
             [4,11],[4,12],[4,13]]                                                  #         4
           ]

TrackCurr  = 1
FolderCurr = 1
PListCurr  = 0
IDLE       = 0
PlayMode   = IDLE
ListLen    = 0
ListCnt    = 0

#BLRemote   = {0x07:[99,1], 0x08:[1,2], 0x09:[99,2], 0x0C:[2,2],  0x0D:[2,8],  0x16:[2,5],  0x18:[2,9],  0x19:[2,13],
#              0x1C:[2,17], 0x40:[3,2], 0x42:[3,12], 0x43:[3,20], 0x44:[1,4],  0x45:[1,11], 0x47:[1,2],  0x4A:[2,19],
#              0x52:[2,16], 0x5A:[2,15],0x5E:[3,10] }
SonyRemote   = {0x12:[99,1], 0x13:[99,2], 0x14:[99,3], 0x10:[99,1], 0x11:[99,2], 0x25:[3,3],  0x26:[2,1],  0x7C:[2,19], 0x15:[1,11],
                0x15:[2,13], 0x77:[2,5],  0x3A:[2,5],  0x4D:[1,8],  0x3B:[3,19], 0x65:[1,1],  0x24:[1,2],  0x4B:[1,3],  0x5B:[1,6],
                0x23:[1,7],  0x60:[1,12], 0x73:[1,10], 0x17:[1,4],  0x28:[1,7],  0x1A:[4,1],  0x1B:[4,13],
                0x56:[4,12], 0x3C:[4,11], 0x19:[4,10], 0x3D:[4,9],  0x18:[4,8],  0x76:[4,7],  0x1D:[4,6],  0x3E:[4,5],
                0x01:[3,19], 0x02:[3,20], 0x03:[3,5],  0x04:[3,10], 0x05:[3,12], 0x06:[2,9],  0x07:[2,16], 0x08:[2,21], 0x09:[2,18] }      

# now actually create the instance, reset and read stored volume data
player=DFPlayer(UART_INSTANCE, TX_PIN, RX_PIN, BUSY_PIN)
player.reset()
VolCurr = ReadVol()
print(f"read {VolCurr}")

# setup IR Remote callback
#ir = NEC_16(Pin(5, Pin.IN), ir_callback)
ir_data = 0
ir_addr = 0
ir = SONY_20(Pin(Irs, Pin.IN), ir_callback)

    
######################################################################
# RFID MFRC522 reader
######################################################################  
reader = MFRC522(spi_id=0,sck=2,miso=4,mosi=3,cs=1,rst=0)
TagPrvCard = [0]
TagCmd     = 0
TagVal1    = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18]
TagVal2    = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18]
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
#sleep(3)
#BtnLedOff(BtnArr)
FirstFlag = True
print("Go");

while (TestOne == True):
    BtnLedOff(BtnArr)
    sleep(1)
    BtnLedOn(BtnArr)
    sleep(1)
    
while (TestTwo == True):
    sleep(3)
    print("play test track")
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



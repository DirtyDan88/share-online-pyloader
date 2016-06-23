#!/usr/bin/env python3

#==============================================================================#
#                        --- share-online-pyloader ---                         #
#                             author:  Max Stark                               #
#                             date:    03.06.2016                              #
#                             version: 2.0                                     #
#==============================================================================#

import sys, signal, argparse, curses, os, time, re, io
import requests, subprocess, rarfile
from queue     import PriorityQueue, Empty
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

USERNAME = '' # enter username here
PASSWORD = '' # enter password here

#===============================================================================
class DownloadStatus:
  INITIALIZED = 8
  NOTFOUND = 6
  WAITING = 5
  RUNNING = 2
  MD5CHECK = 3
  COMPLETE = 7
  EXTRACTING = 9
  FINISHED = 10
  FAILED = 4
  CANCELED = 1

#===============================================================================
class Download:
  QUEUE_POS = 0
  COMPLETE_DOWNLOADS = 0
  def __init__(self, linkID):
    self.terminated = False
    self.__path = ''
    self.__shortName = ' [' + 25*'-' + ']'
    self.__formattedSize = '-'*6
    self.__linkID = linkID
    self.__queuePos = Download.QUEUE_POS
    Download.QUEUE_POS += 1
    self.__extractThread = None
    self.__setStatus(DownloadStatus.INITIALIZED, 'link-id: ' + linkID)
  #_____________________________________________________________________________
  def requestLinkMetaData(self):
    url = 'http://api.share-online.biz/cgi-bin?q=linkdata&username=' + \
           USERNAME + '&password=' + PASSWORD + '&lid=' + self.__linkID
    response = requests.get(url)
    #time.sleep(0.1)
    if response.status_code == 200:
      if response.text.startswith('**'):
        self.__setStatus(DownloadStatus.NOTFOUND, response.text)
      else:
        if not self.__parseLinkMetdaData(response):
          self.__setStatus(DownloadStatus.NOTFOUND, 'parsing error')
        elif self.__linkstatus != 'online':
          self.__setStatus(DownloadStatus.CANCELED, self.__linkstatus + \
                                             ' (' + self.__url + ')')
        else:
          if self.__status == DownloadStatus.INITIALIZED:
            if not self.__isComplete():
              self.__setStatus(DownloadStatus.WAITING)
    else:
      self.__setStatus(DownloadStatus.NOTFOUND, 'network error')
  #_____________________________________________________________________________
  def __parseLinkMetdaData(self, response):
    lines = response.text.split('\n')
    complete = 0
    for line in lines:
      if line.startswith('STATUS:'):
        self.__linkstatus = line.split('STATUS:')[1].strip()
        complete += 1
      if line.startswith('URL:'):
        self.__url = line.split('URL:')[1].strip()
        complete += 1
      elif line.startswith('NAME:'):
        self.name = line.split('NAME:')[1].strip()
        self.__shortName = ' [' + self.name[:10] + '...' + self.name[-12:] + ']'
        self.__path = DOWNLOADMANAGER.downloadDirectory + '/' + self.name
        complete += 1
      elif line.startswith('SIZE:'):
        self.__sizeInByte = int(line.split('SIZE:')[1].strip())
        sizeInMB = self.__sizeInByte / (1000*1000)
        self.__formattedSize = '{:>6}'.format('{:.6}'.format( \
                               str('{0:.2f}'.format(sizeInMB))))
        complete += 1
      elif line.startswith('MD5:'):
        self.__md5 = line.split('MD5:')[1].strip()
        complete += 1
    if complete != 5:
      return False
    return True
  #_____________________________________________________________________________
  def removeFile(self):
    if os.path.exists(self.__path):
      os.remove(self.__path)
  #_____________________________________________________________________________
  def getStatus(self):
    return self.__status
  #_____________________________________________________________________________
  def __setStatus(self, status, statusMessage = ''):
    self.__status = status
    self.__statusMessage = statusMessage
    if self.__status == DownloadStatus.NOTFOUND:
      self.terminated = True
    elif self.__status == DownloadStatus.WAITING:
      DOWNLOADMANAGER.queuedDownloads.put((self.__queuePos, self))
    elif self.__status == DownloadStatus.COMPLETE:
      if self.__extractThread is None:
        Download.COMPLETE_DOWNLOADS += 1
        self.__extractThread = Thread(target=self.__extract)
        self.__extractThread.start()
    elif self.__status == DownloadStatus.FINISHED:
      self.terminated = True
    elif self.__status == DownloadStatus.FAILED:
      DOWNLOADMANAGER.queuedDownloads.put((self.__queuePos, self))
    elif self.__status == DownloadStatus.CANCELED:
      self.terminated = True
  #_____________________________________________________________________________
  def toString(self):
    if self.__status == DownloadStatus.INITIALIZED or \
       self.__status == DownloadStatus.NOTFOUND:
      return self.__shortName + '   ' + self.__statusMessage
    else:
      return self.__shortName + '   ' + \
             self.__getStatusString() + '   ' + \
             self.__getProgressString()
  #_____________________________________________________________________________
  def __getStatusString(self):
    if self.__status == DownloadStatus.WAITING:
      return '{:<29}'.format('{:.29}'.format('waiting for a free slot'))
    elif self.__status == DownloadStatus.RUNNING:
      return self.__getProgressAnimation(29)
    elif self.__status == DownloadStatus.MD5CHECK:
      return '{:<29}'.format('{:.29}'.format('md5-check ' + \
                                             '*'*(int(time.time()) % 4)))
    elif self.__status == DownloadStatus.COMPLETE:
      return '{:<29}'.format('{:.29}'.format('waiting for missing parts ' + \
                                             '*'*(int(time.time()) % 4)))
    elif self.__status == DownloadStatus.EXTRACTING:
      return '{:<29}'.format('{:.29}'.format('extracting ' + \
                                             '*'*(int(time.time()) % 4)))
    elif self.__status == DownloadStatus.FINISHED:
      return '[' + '{:=^27}'.format(' ' + self.__statusMessage + ' ') + ']'
    elif self.__status == DownloadStatus.FAILED:
      return '{:<29}'.format('{:.29}'.format('FAILED: ' + self.__statusMessage))
    elif self.__status == DownloadStatus.CANCELED:
      return '{:<29}'.format('{:.29}'.format('CANCELED: ' + \
                                             self.__statusMessage))
  #_____________________________________________________________________________
  def __getProgressAnimation(self, space):
    space -= 2 #29
    completed = round((space / 100) * self.__getProgressInPercent())
    due = space - completed - 1
    if due < 0:
      due = 0
      completed -= 1
    s1 = '='
    s2 = '>' if int(time.time()) % 2 == 0 else ' '
    s3 = ' '
    return '[' + s1*completed + s2 + s3*due + ']'
  #_____________________________________________________________________________
  def __getProgressInPercent(self):
    if os.path.exists(self.__path):
      sizeInBytes = int(os.stat(self.__path).st_size)
      return int((100 * sizeInBytes) / self.__sizeInByte)
    return 0
  #_____________________________________________________________________________
  def __getProgressString(self):
    if os.path.exists(self.__path):
      fileSizeInMB = (os.stat(self.__path).st_size) / (1000*1000)
      formattedFileSize = '{:>6}'.format('{:.6}'.format( \
                          str('{0:.2f}'.format(fileSizeInMB))))
      return '[' + formattedFileSize + '/' + self.__formattedSize + 'MB]'
    return '[------/' + self.__formattedSize + 'MB]'
  #_____________________________________________________________________________
  def start(self):
    self.requestLinkMetaData() # renew download ticket
    self.__setStatus(DownloadStatus.RUNNING)

    if os.path.exists(self.__path):
      resume = {'Range':'bytes=' + str(os.stat(self.__path).st_size) + '-'}
      retCode = 206
    else:
      resume = {}
      retCode = 200

    req = requests.get(self.__url, cookies=COOKIE.get(), \
                        headers=resume, stream=True)
    if req.status_code == retCode:
      CHUNK_SIZE = 8192
      with open(self.__path, 'ab') as f:
        for chunk in req.iter_content(CHUNK_SIZE):
          if not self.__status == DownloadStatus.RUNNING: break
          f.write(chunk)
    req.close()

    if not self.__status == DownloadStatus.CANCELED and \
       not self.__status == DownloadStatus.WAITING:
      if not self.__isComplete():
        self.__setStatus(DownloadStatus.FAILED, 'unknown')
  #_____________________________________________________________________________
  def __isComplete(self):
    if os.path.exists(self.__path):
      fileSizeInByte = int(os.stat(self.__path).st_size)
      if fileSizeInByte >= self.__sizeInByte:
        if self.__md5Check():
          self.__setStatus(DownloadStatus.COMPLETE, 'checksum ok')
        else:
          self.__setStatus(DownloadStatus.FAILED, 'checksum-error')
        return True
    return False
  #_____________________________________________________________________________
  def __md5Check(self):
    self.__setStatus(DownloadStatus.MD5CHECK)
    md5Result = subprocess.check_output(['md5sum', self.__path])
    checksum = md5Result.decode("utf-8").split(' ')[0]
    if checksum != self.__md5:
      return False
    return True
  #_____________________________________________________________________________
  def __extract(self):
    if not EXTRACT:
      self.__setStatus(DownloadStatus.FINISHED, 'checksum ok')
    else:
      self.__tryExtracting()
  #_____________________________________________________________________________
  def __tryExtracting(self):
      while not self.terminated:
        try:
          rf = rarfile.RarFile(self.__path)
          self.__setStatus(DownloadStatus.EXTRACTING)
          rf.extractall(path = DOWNLOADMANAGER.downloadDirectory, pwd = RARPWD)
          self.__setStatus(DownloadStatus.FINISHED, 'extracted')
        except rarfile.NeedFirstVolume:
          self.__setStatus(DownloadStatus.FINISHED, 'checksum ok')
        except (rarfile.RarCRCError, rarfile.RarUserBreak) as e:
          self.__setStatus(DownloadStatus.COMPLETE)
          if not self.__retryDelay(): break
          continue
        except rarfile.RarCannotExec:
          self.__setStatus(DownloadStatus.CANCELED, 'unrar is not installed')
  #_____________________________________________________________________________
  def __retryDelay(self):
    complete_downloads = Download.COMPLETE_DOWNLOADS
    sec = 1200
    while sec >= 0 and complete_downloads == Download.COMPLETE_DOWNLOADS:
      if self.terminated: return False
      time.sleep(1)
      sec -= 1
    return True
  #_____________________________________________________________________________
  def pause(self):
    self.__setStatus(DownloadStatus.WAITING)
  #_____________________________________________________________________________
  def cancel(self):
    if self.__status == DownloadStatus.FAILED:
      self.terminated = True
    else:
      self.__setStatus(DownloadStatus.CANCELED, 'user canceled')

#===============================================================================
class DownloadSlot(Thread):
  def __init__(self, slotID):
    Thread.__init__(self)
    self.__slotID = ' [Slot-' + str(slotID + 1) + '] '
    self.__status = 'initialized'
    self.__paused = False
    self.__curDownload = None
  #_____________________________________________________________________________
  def run(self):
    while not DOWNLOADMANAGER.allDownloadsTerminated():
      if not self.__paused:
        try:
          self.__handleDownload()
        except Empty:
          animation = '*'*(int(time.time()) % 4)
          self.__status = 'idle mode (queue empty) ' + animation
      self.__curDownload = None
      time.sleep(1)
    self.__status = 'terminated'
  #_____________________________________________________________________________
  def __handleDownload(self):
    self.__curDownload = DOWNLOADMANAGER.queuedDownloads.get_nowait()[1]
    if self.__curDownload.getStatus() == DownloadStatus.FAILED:
      if not self.__retryDelay(): return
      self.__curDownload.removeFile()
      #self.__curDownload.requestLinkMetaData()
    self.__status = 'downloading ' + self.__curDownload.name
    self.__curDownload.start()
  #_____________________________________________________________________________
  def __retryDelay(self):
    sec = 60
    while sec >= 0:
      if self.__curDownload.terminated: return False
      self.__status = 'retry ' + self.__curDownload.name + \
                      ' in ' + str(sec) + 's'
      time.sleep(1)
      sec -= 1
    return True
  #_____________________________________________________________________________
  def pause(self):
    self.__paused = True
    self.__status = 'paused'
    if not self.__curDownload is None:
      self.__curDownload.pause()
  #_____________________________________________________________________________
  def unpause(self):
    self.__paused = False
    self.__status = 'unpaused'
  #_____________________________________________________________________________
  def getStatusString(self):
    return self.__slotID + self.__status

#===============================================================================
class DownloadManager:
  def __init__(self):
    self.downloadSlots = []
    self.allDownloads = []
    self.queuedDownloads = PriorityQueue()
    self.packageName = ''
    self.isPaused = False
  #_____________________________________________________________________________
  def init(self, linkListFileName):
    try:
      linkListFile = open(linkListFileName, 'r')
    except (IOError, OSError):
      return False
    self.__setPackageName(linkListFile.readline())
    self.__parseLinkList(linkListFile.readlines())
    return True
  #_____________________________________________________________________________
  def __setPackageName(self, packageName):
    self.packageName = packageName.split('package:')[1].strip()
    self.downloadDirectory = self.packageName.replace(' ', '.')
    if not os.path.exists(self.downloadDirectory):
      os.makedirs(self.downloadDirectory)
  #_____________________________________________________________________________
  def __parseLinkList(self, linkList):
    for link in linkList:
      if not link.startswith('#'):
        if re.match('^http:\/\/[www.]*share-online.biz\/dl', link):
          linkID = link.split('dl/')[1].strip()
          self.allDownloads.append(Download(linkID))
  #_____________________________________________________________________________
  def start(self, numDownloadSlots):
    thread = Thread(target=self.__requestLinkMetaData, args=(numDownloadSlots,))
    thread.start()
    for slotNum in range(0, numDownloadSlots):
      slot = DownloadSlot(slotNum)
      slot.start()
      self.downloadSlots.append(slot)
  #_____________________________________________________________________________
  def __requestLinkMetaData(self, numDownloadSlots):
    with ThreadPoolExecutor(max_workers=numDownloadSlots) as executor:
      for download in self.allDownloads:
        if TERMINATED:
          if not download.terminated:
            download.cancel()
          return
        executor.submit(download.requestLinkMetaData)
  #_____________________________________________________________________________
  def pause(self):
    self.isPaused = True
    for slot in self.downloadSlots:
      slot.pause()
  #_____________________________________________________________________________
  def unpause(self):
    self.isPaused = False
    for slot in self.downloadSlots:
      slot.unpause()
  #_____________________________________________________________________________
  def stop(self):
    for download in self.allDownloads:
      if not download.terminated:
        download.cancel()
    for slot in self.downloadSlots:
      slot.join()
  #_____________________________________________________________________________
  def allDownloadsTerminated(self):
    for download in self.allDownloads:
      if not download.terminated:
        return False
    return True

#===============================================================================
class Cookie(Thread):
  def __init__(self):
    Thread.__init__(self)
    self.__cookie = None
  #_____________________________________________________________________________
  def run(self):
    expireTime = 0
    while not TERMINATED:
      if expireTime > 0:
        expireTime -= 1
      else:
        self.__requestCookie()
        expireTime = 1800
      time.sleep(1)
  #_____________________________________________________________________________
  def __requestCookie(self):
    url = 'http://api.share-online.biz/cgi-bin?q=userdetails&' + \
          'username=' + USERNAME + '&password=' + PASSWORD
    response = requests.get(url)
    if response.status_code == 200:
      lines = response.text.split('\n')
      for line in lines:
        if line.startswith('a='):
          cookie = line.split('=')[1]
          if cookie != 'not_available':
            self.__cookie = dict(a=cookie)
            return
    terminate('could not get cookie')
  #_____________________________________________________________________________
  def get(self):
    return self.__cookie

#===============================================================================
class UserInterface:
  def __init__(self):
    sys.stderr = open('stderr.log', 'w')
    self.__showFrom = 0
    self.__rowsHeader = 0
    self.__rows, columns = os.popen('stty size', 'r').read().split()
    self.__rows = int(self.__rows)
  #_____________________________________________________________________________
  def start(self):
    self.__ui = curses.initscr()
    self.__ui.keypad(1)
    curses.noecho()
    curses.cbreak()
    self.__printloop = Thread(target=self.__printloop)
    self.__printloop.start()
  #_____________________________________________________________________________
  def __printloop(self):
    while not TERMINATED:
      self.__ui.clear()
      self.__printPreamble()
      self.__printHeader()
      self.__printDownloads()
      self.__printStats()
      self.__ui.refresh()
      sys.stderr.flush()
      time.sleep(0.1)
  #_____________________________________________________________________________
  def __printPreamble(self):
    self.__ui.addstr(0, 0, '='*80)
    s1 = 'Max Stark | June 2016 | see license for legal restrictions'
    s1 = s1 if len(s1) % 2 == 0 else s1 + ' '
    num = (80 - len(s1) - 6) // 2
    self.__ui.addstr(1, 0, '===' + ' '*num + s1 + ' '*num + '===')
    s2 = '--- share-online-pyloader v2.0 ---'
    s2 = s2 if len(s2) % 2 == 0 else s2 + ' '
    num = (80 - len(s2) - 6) // 2
    self.__ui.addstr(2, 0, '===' + ' '*num + s2 + ' '*num + '===' + '\n')
    self.__ui.addstr(3, 0, '='*80)
  #_____________________________________________________________________________
  def __printHeader(self):
    self.__rowsHeader = 4
    self.__ui.addstr(self.__rowsHeader, 0, \
                     ' package-name: ' + DOWNLOADMANAGER.packageName)
    for slot in DOWNLOADMANAGER.downloadSlots:
      self.__rowsHeader += 1
      self.__ui.addstr(self.__rowsHeader, 0, slot.getStatusString())
  #_____________________________________________________________________________
  def __printDownloads(self):
    self.__showTo = self.__showFrom + self.__rows - (self.__rowsHeader + 2 + 4)
    showDownloads = DOWNLOADMANAGER.allDownloads[self.__showFrom:self.__showTo]
    row = self.__rowsHeader + 2
    for download in showDownloads:
      self.__ui.addstr(row, 0, download.toString())
      row += 1
  #_____________________________________________________________________________
  def __printStats(self):
    totalNum = len(DOWNLOADMANAGER.allDownloads)
    waitingNum = DOWNLOADMANAGER.queuedDownloads.qsize()
    activeNum = len(list(filter( \
                  lambda d: d.getStatus() == DownloadStatus.RUNNING, \
                  DOWNLOADMANAGER.allDownloads
                )))
    completedNum = totalNum - waitingNum - activeNum
    self.__ui.addstr(self.__rows - 4, 0, '='*80)
    s1 = 'total=' + str(totalNum) + ' | ' + \
         'waiting=' + str(waitingNum) + ' | ' + \
         'active=' + str(activeNum) + ' | ' + \
         'complete=' + str(completedNum)
    s1 = s1 if len(s1) % 2 == 0 else s1 + ' '
    num = (80 - len(s1) - 6) // 2
    self.__ui.addstr(self.__rows - 3, 0, '===' + ' '*num + s1 + ' '*num + '===')
    s2 = 'show from ' + str(self.__showFrom+1) + ' to ' + str(self.__showTo) + \
         ' | hit "p" to pause/unpause | hit "q" to quit'
    s2 = s2 if len(s2) % 2 == 0 else s2 + ' '
    num = (80 - len(s2) - 6) // 2
    self.__ui.addstr(self.__rows - 2, 0, '===' + ' '*num + s2 + ' '*num + '===')
    self.__ui.addstr(self.__rows - 1, 0, '='*80)
  #_____________________________________________________________________________
  def keyloop(self):
    key = ''
    while not TERMINATED:
      key = self.__ui.getch()
      if key == curses.KEY_UP:
        if self.__showFrom > 0:
          self.__showFrom -= 1
      elif key == curses.KEY_DOWN:
        if self.__showFrom < (len(DOWNLOADMANAGER.allDownloads) - \
                            (self.__rows - self.__rowsHeader - 2 - 4)):
          self.__showFrom += 1
      elif key == ord('p'):
        if DOWNLOADMANAGER.isPaused:
          DOWNLOADMANAGER.unpause()
        else:
          DOWNLOADMANAGER.pause()
      elif key == ord('q'):
        if not TERMINATED:
          terminate()
  #_____________________________________________________________________________
  def stop(self):
    self.__printloop.join()
    curses.endwin()
    sys.stderr.flush()
    if int(os.stat('stderr.log').st_size) == 0:
      os.remove('stderr.log')

#===============================================================================
def handlerForSIGINT(signal, frame):
  terminate()

#===============================================================================
def terminate(errorMessage = None):
  global TERMINATED
  TERMINATED = True
  DOWNLOADMANAGER.stop()
  USERINTERFACE.stop()
  if errorMessage != None:
    print('\n!! error: ' + errorMessage + ' !!')

#===============================================================================
TERMINATED = False
EXTRACT = False
RARPWD = None
COOKIE = Cookie()
DOWNLOADMANAGER = DownloadManager()
USERINTERFACE = UserInterface()

if __name__ == '__main__':
  signal.signal(signal.SIGINT, handlerForSIGINT)

  parser = argparse.ArgumentParser()
  parser.add_argument('-s', action='store',
               help = 'number of download-slots', default = '1')
  parser.add_argument('-e', action='store_true',
               help = 'extract files after downloading', default = False)
  parser.add_argument('-p', action='store',
               help = 'password for archieves (set in \'\')', default = None)
  parser.add_argument('linkListFileName',
               help = 'file with link-ids')
  args = parser.parse_args()
  EXTRACT = args.e
  RARPWD = args.p

  COOKIE.start()
  USERINTERFACE.start()
  if DOWNLOADMANAGER.init(args.linkListFileName):
    DOWNLOADMANAGER.start(int(args.s))
    USERINTERFACE.keyloop()
  else:
    terminate('"' + args.linkListFileName + '" is not a file ')

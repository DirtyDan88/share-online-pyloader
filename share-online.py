#!/usr/bin/env python3

#==============================================================================#
#                        --- share-online-pyloader ---                         #
#                             author:  Max Stark                               #
#                             date:   16.02.2016                               #
#==============================================================================#

import sys, os, time, requests, subprocess, re, argparse
from multiprocessing import Queue
from threading       import Thread

USERNAME = '' # enter username here
PASSWORD = '' # enter password here
COOKIE   = ''

FILEQUEUE = Queue()
ACTIVE_DOWNLOADS = []
THREADS = []
NUM_FAILED_DOWNLOADS = 0
PRINT_NEWLINE = False

#===============================================================================
def printPreamble():
  print('='*80)
  s1 = 'Max Stark | Feb 2016 | see license for legal restrictions'
  s1 = s1 if len(s1) % 2 == 0 else s1 + ' '
  num = (80 - len(s1) - 6) // 2
  print('===' + ' '*num + s1 + ' '*num + '===')
  s2 = '--- share-online-pyloader ---'
  s2 = s2 if len(s2) % 2 == 0 else s2 + ' '
  num = (80 - len(s2) - 6) // 2
  print('===' + ' '*num + s2 + ' '*num + '===')
  print('='*80)

#===============================================================================
def setCookie():
  print('## requesting cookie for user ' + USERNAME)
  url = 'http://api.share-online.biz/cgi-bin?q=userdetails&' + \
        'username=' + USERNAME + '&password=' + PASSWORD
  response = requests.get(url)
  if response.status_code == 200:
    lines = response.text.split('\n')
    for line in lines:
      if line.startswith('a='):
        global COOKIE
        COOKIE = line
        return
  sys.exit('!! could not set cookie, abort')

#===============================================================================
def readLinkIDs(fileName):
  linkIDs = open(fileName, 'r')
  
  packageName = linkIDs.readline().split('package:')[1].strip()
  dirName = packageName.replace(' ', '.')
  print('## package: ' + packageName)

  if not os.path.exists(dirName):
    os.makedirs(dirName)
  
  lines = linkIDs.readlines()

  numTotalLinkIDs = 0
  for line in lines:
    if re.match('^http:\/\/[www.]*share-online.biz\/dl', line):
      numTotalLinkIDs += 1

  numCurrentLinkID = 0
  for line in lines:
    if re.match('^http:\/\/[www.]*share-online.biz\/dl', line):
      numCurrentLinkID += 1
      sys.stdout.write('\r## requesting link meta-data ' + \
                        str(numCurrentLinkID) + '/' + str(numTotalLinkIDs))
      sys.stdout.flush()
      
      linkID = line.split('dl/')[1].strip()
      f = DownloadableFile(linkID, dirName)
      global FILEQUEUE
      FILEQUEUE.put(f)
  print('')

  return dirName

#===============================================================================
class DownloadableFile:
  def __init__(self, linkID, dirName):
    self.linkID = linkID
    self.getMetaData()
    self.path = dirName + '/' + self.name

  #_____________________________________________________________________________
  def getMetaData(self):
    url = 'http://api.share-online.biz/cgi-bin?q=linkdata&username=' + \
           USERNAME + '&password=' + PASSWORD + '&lid=' + self.linkID
    response = requests.get(url)
    if response.status_code == 200:
      lines = response.text.split('\n')
      for line in lines:
        if line.startswith('STATUS:'):
          self.status = line.split('STATUS:')[1].strip()
        if line.startswith('URL:'):
          self.url = line.split('URL:')[1].strip()
        if line.startswith('NAME:'):
          self.name = line.split('NAME:')[1].strip()
        if line.startswith('SIZE:'):
          self.size = int(line.split('SIZE:')[1].strip())
    else:
      sys.exit('!! could not get link meta-data, abort')
  #_____________________________________________________________________________
  def downloadFinished(self):
    if os.path.exists(self.path):
      size = int(os.stat(self.path).st_size)
      if size == self.size:
        return True
    return False
  #_____________________________________________________________________________
  def getProgress(self):
    if os.path.exists(self.path):
      size = int(os.stat(self.path).st_size)
      return int((100 * size) / self.size)
    return 0
  #_____________________________________________________________________________
  def download(self, callback, slot):
    self.slot = str(slot)
    global ACTIVE_DOWNLOADS
    ACTIVE_DOWNLOADS.append(self)

    if self.downloadFinished():
      print('    [' + self.slot + '] ## already finished:  ' + self.name)
    else:
      printNewline()
      print('    [' + self.slot + '] >> downloading file:  ' + self.name)
      cmd = 'curl -s \'' + self.url + '\' --cookie ' + COOKIE + \
            ' > ' + self.path
      subprocess.call(cmd, shell=True)

      if self.downloadFinished():
        printNewline()
        print('    [' + self.slot + '] ++ finished download: ' + self.name)
      else:
        printNewline()
        print('    [' + self.slot + '] !! download failed:   ' + self.name)
        global NUM_FAILED_DOWNLOADS
        NUM_FAILED_DOWNLOADS += 1    

    ACTIVE_DOWNLOADS.remove(self)
    callback(slot)

#===============================================================================
def printProgress():
  global PRINT_NEWLINE
  s1 = '+'
  
  while len(ACTIVE_DOWNLOADS) > 0:
    time.sleep(0.5)

    s1 = '-' if s1 == '+' else '+'
    s2 = '        '
    for download in sorted(ACTIVE_DOWNLOADS, key=lambda d: d.slot):
      progress = download.getProgress()
      progress = 10 if progress >  97 else progress // 10
      s3       = '' if progress == 10 else s1
      s2 += '[' + download.slot + ']' + \
            '[' + '#'*(progress) + s3 + '-'*(9-progress) + '] '

    sys.stdout.write('\r' + s2)
    sys.stdout.flush()
    PRINT_NEWLINE = True

  PRINT_NEWLINE = False  

#===============================================================================
def printNewline():
  global PRINT_NEWLINE
  if PRINT_NEWLINE:
    print('')
    PRINT_NEWLINE = False

#===============================================================================
def downloadNext(slot):
  if not FILEQUEUE.empty():
    f = FILEQUEUE.get()
    thread = Thread(target=f.download, args=(downloadNext, slot))
    thread.start()
    global THREADS
    THREADS.append(thread)
  else:
    print('    [' + str(slot) + '] ## file-queue is empty')
    
#===============================================================================
def runDownloads(downloadSlots):
  print('## start downloading with [' + str(downloadSlots) + ' download-slots]')
  progressPrinting = Thread(target=printProgress, args=[])

  global THREADS
  THREADS = []

  downloads = 0
  while downloads < downloadSlots:
    downloads += 1
    downloadNext(downloads)

  progressPrinting.start()

  for thread in THREADS:
    thread.join()
  progressPrinting.join()

#===============================================================================
def retryDelay():
  sec = 60
  while sec >= 0:
    sys.stdout.write('\r## ' + str(NUM_FAILED_DOWNLOADS) + ' downloads ' + \
                     'failed, retry in ' + str(sec) + 's ')
    sys.stdout.flush()
    time.sleep(1)
    sec -= 1
  print('')

#===============================================================================
def download(linkListFileName, downloadSlots):
  global NUM_FAILED_DOWNLOADS

  while True:
    NUM_FAILED_DOWNLOADS = 0
    setCookie()
    dirName = readLinkIDs(linkListFileName)
    runDownloads(downloadSlots)

    if NUM_FAILED_DOWNLOADS > 0:
      retryDelay()
      print('='*80)
    else:
      break

  print('\r## finished all downloads')
  return dirName

#===============================================================================
def extract(dirName, passWord):
  print('## try to extract files')
  os.chdir(dirName)

  if passWord:
    passWord = '-p\'' + passWord + '\' '

  for root, dirs, fileNames in os.walk('.'):
    for fileName in fileNames:
      if re.match('.*part[0]*1.rar', fileName):
        print('    >> extract file: ' + fileName)
        cmd = 'unrar e ' + passWord + '-o- -inul ' + fileName
        subprocess.call(cmd, shell=True)

  os.chdir('..')
  print('## finished')

#===============================================================================
if __name__ == '__main__':
  printPreamble()

  parser = argparse.ArgumentParser()
  parser.add_argument('-s', action='store', 
               help = 'number of download-slots', default = '1')
  parser.add_argument('-e', action='store_true',
               help = 'extract files after downloading', default = False)
  parser.add_argument('-p', action='store',
               help = 'password for archieves (set in \'\')', default = '')
  parser.add_argument('linkListFileName', 
               help = 'file with link-ids')
  args = parser.parse_args()

  dirName = download(args.linkListFileName, int(args.s))
  if args.e:
    extract(dirName, args.p)


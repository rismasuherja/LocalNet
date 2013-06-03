# -*- coding: latin-1 -*-

from interfaces import MessageReceiverInterface
import time, threading
from twython import Twython
from OSC import OSCClient, OSCMessage, OSCServer, getUrlStr

class SmsReceiver(MessageReceiverInterface):
    """A class for receiving SMS messages and passing them to its subscribers"""

class HttpReceiver(MessageReceiverInterface):
    """A class for receiving json/xml query results and passing them to its subscribers"""

class OscReceiver(MessageReceiverInterface):
    """A class for receiving Osc messages and passing them to its subscribers"""
    OSC_SERVER_IP = "127.0.0.1"
    OSC_SERVER_PORT = 8888

    def __init__(self, others):
        MessageReceiverInterface.__init__(self)
        ## this is a dict of names to receivers
        ## like: 'sms' -> SmsReceiver_instance
        ## keys are used to match against osc requests
        self.otherReceivers = others
        self.otherReceivers['osc'] = self

    def __oscHandler(self, addr, tags, stuff, source):
        addrTokens = addr.lstrip('/').split('/')
        ## /LocalNet/{Add,Remove}/Type -> port-number
        if ((addrTokens[0].lower() == "localnet")
            and (addrTokens[1].lower() == "add")):
            ip = getUrlStr(source).split(":")[0]
            port = stuff[0]
            if (addrTokens[2].lower() in self.otherReceivers):
                print "adding "+ip+":"+port+" to "+addrTokens[2].lower()+" receivers"
                self.otherReceivers[addrTokens[2].lower()].addSubscriber((ip,port))
        elif ((addrTokens[0].lower() == "localnet")
              and (addrTokens[1].lower() == "remove")):
            ip = getUrlStr(source).split(":")[0]
            port = stuff[0]
            if (addrTokens[2].lower() in self.otherReceivers):
                print "removing "+ip+" from "+addrTokens[2].lower()+" receivers"
                self.otherReceivers[addrTokens[2].lower()].removeSubscriber((ip,port))
        ## /LocalNet/ListReceivers -> port-number
        elif ((addrTokens[0].lower() == "localnet")
              and (addrTokens[1].lower().startswith("list"))):
            ip = getUrlStr(source).split(":")[0]
            port = stuff[0]
            ## send list of receivers to client
            msg = OSCMessage()
            msg.setAddress("/LocalNet/Receivers")
            msg.append(",".join(self.otherReceivers.keys()))
            self.oscClient.sendto(msg, (ip, int(port)))
        ## /AEffectLab/{local}/{type} -> msg
        elif (addrTokens[0].lower() == "aeffectlab"):
            print "forwarding "+addr+" : "+str(stuff[0])+" to my osc subscribers"
            ## setup osc message
            msg = OSCMessage()
            msg.setAddress("/AEffectLab/"+addrTokens[1]+"/"+addrTokens[2])
            msg.append(str(stuff[0]))
            ## send to subscribers
            for (ip,port) in self.subscriberList:
                self.oscClient.sendto(msg, (ip, port))

    ## setup osc server
    def setup(self, osc, loc):
        self.oscClient = osc
        self.location = loc
        self.oscServer = OSCServer((OscReceiver.OSC_SERVER_IP,
                                    OscReceiver.OSC_SERVER_PORT))
        ## handler
        self.oscServer.addMsgHandler('default', self.__oscHandler)
        ## start server
        self.oscThread = threading.Thread( target = self.oscServer.serve_forever )
        self.oscThread.start()

    ## end oscReceiver
    def stop(self):
        self.oscServer.close()
        self.oscThread.join()

class TwitterReceiver(MessageReceiverInterface):
    """A class for receiving Twitter messages and passing them to its
    subscribers"""
    ## How often to check twitter (in seconds)
    TWITTER_CHECK_PERIOD = 6
    ## What to search for
    SEARCH_TERM = ("#ficaadica OR aeLab")

    ## setup twitter connection and internal variables
    def setup(self, osc, loc):
        self.oscClient = osc
        self.location = loc
        self.lastTwitterCheck = time.time()
        self.mTwitter = None
        self.twitterAuthenticated = False
        self.largestTweetId = 1
        self.twitterResults = None
        ## read secrets from file
        inFile = open('oauth.txt', 'r')
        self.secrets = {}
        for line in inFile:
            (k,v) = line.split()
            self.secrets[k] = v
        self.__authenticateTwitter()
        ## get largest Id for tweets that came before starting the program
        self.__searchTwitter()
        self.__getLargestTweetId()
        self.twitterResults = None

    ## check for new tweets every once in a while
    def update(self):
        if (time.time() - self.lastTwitterCheck > TwitterReceiver.TWITTER_CHECK_PERIOD):
            self.__searchTwitter()
            if (not self.twitterResults is None):
                for tweet in self.twitterResults["statuses"]:
                    ## print
                    print ("pushing %s from @%s" %
                           (tweet['text'],
                            tweet['user']['screen_name']))
                    ## setup osc message
                    msg = OSCMessage()
                    msg.setAddress("/AEffectLab/"+self.location+"/Twitter")
                    msg.append(tweet['text'])
                    ## send to subscribers
                    for (ip,port) in self.subscriberList:
                        self.oscClient.sendto(msg, (ip, port))
                    ## TODO: log on local database
                    ## update largestTweetId for next searches
                    if (int(tweet['id']) > self.largestTweetId):
                        self.largestTweetId = int(tweet['id'])
            self.lastTwitterCheck = time.time()

    ## authenticate to twitter using secrets
    def __authenticateTwitter(self):
        try:
            self.mTwitter = Twython(twitter_token = self.secrets['CONSUMER_KEY'],
                                    twitter_secret = self.secrets['CONSUMER_SECRET'],
                                    oauth_token = self.secrets['ACCESS_TOKEN'],
                                    oauth_token_secret = self.secrets['ACCESS_SECRET'])
            self.twitterAuthenticated = True
        except:
            self.mTwitter = None
            self.twitterAuthenticated = False

    ## get largest Id for tweets in twitterResults
    def __getLargestTweetId(self):
        if (not self.twitterResults is None):
            for tweet in self.twitterResults["statuses"]:
                print ("Tweet %s from @%s at %s" %
                       (tweet['id'],
                        tweet['user']['screen_name'],
                        tweet['created_at']))
                print tweet['text'],"\n"
                if (int(tweet['id']) > self.largestTweetId):
                    self.largestTweetId = int(tweet['id'])

    ## query twitter
    def __searchTwitter(self):
        if ((self.twitterAuthenticated) and (not self.mTwitter is None)):
            try:
                self.twitterResults = self.mTwitter.search(q=TwitterReceiver.SEARCH_TERM,
                                                           include_entities="false",
                                                           count="50",
                                                           result_type="recent",
                                                           since_id=self.largestTweetId)
            except:
                self.twitterResults = None

if __name__=="__main__":
    o = {}
    tr = TwitterReceiver()
    o['twitter'] = tr
    foo = OscReceiver(o)
    c = OSCClient()
    foo.setup(c,"here")
    tr.setup(c,"here")
    try:
        while(True):
            tr.update()
            time.sleep(5)
    except KeyboardInterrupt :
        foo.stop()

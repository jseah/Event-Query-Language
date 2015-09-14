from __future__ import unicode_literals

try:
    from builtins import bytes, str
except:
    from future.builtins import bytes, str

from datetime import *

import copy
import pprint
keyswithlisttypevalues = ['uuid']
debug = False
debug2 = False
debug3 = False
debug4 = False
class KeyNotFoundError(Exception):
    def __init__(self, message):
        self.message = message

def extract(eventList, keyconstraints):
    '''
    keyconstraints are a list of key-constraint-flags tuples
    flags are lists
    default key will compare the value of the key in the event and return true only if the constraint string is a substring of the key's value in the event
    flags: exact
    
    time keys: starttime, endtime
    time keys need a special flag that determines the comparison to use (>, <, >=, <=, ==)
    default is <=  (times after or same as the constraint)
    time constraints is in datetime format
    '''
    eventfound = []
    for e in eventList:
        eventmatchesconstraints = True
        for keyconstraint in keyconstraints:     #fail event if any keyconstraint fails         
            key = keyconstraint[0]
            constraint = keyconstraint[1]
            flags = keyconstraint[2]
            if key == '':                        #empty keys autopass
                continue
            if not keyinevent(e, key) and not(key == 'ANY'):                    #if event does not have key = autofail
                if 'NOT' in flags:           #continue if flags has 'NOT'
                    continue
                eventmatchesconstraints = False
                break
            constraintmatch = False
            if not(key == 'ANY'):
                if 'ANY' in flags:                  #'ANY' extractor flag means the constraint is a bracket return and if any of the constraints in the bracket matches value, consider it a match
                    for c in constraint:
                        if valuematcheskey(valuefromevent(e, key), key, c, flags):
                            constraintmatch = True
                            break
                else:
                    constraintmatch = valuematcheskey(valuefromevent(e, key), key, constraint, flags)
            else:                   #ANY key searches against all keys in the event
                for eventkey in e:
                    if 'ANY' in flags:
                        for c in constraint:
                            if valuematcheskey(e[eventkey], key, c, flags):
                                constraintmatch = True
                                break
                    if valuematcheskey(e[eventkey], key, constraint, flags):
                        constraintmatch = True
                        break
            if "NOT" in flags:
                constraintmatch = not constraintmatch
            if debug4:
                print("Debug", key, constraintmatch)
            if not constraintmatch:
                eventmatchesconstraints = False
                break
        if eventmatchesconstraints:
            eventfound.append(copy.deepcopy(e))
    #print(eventfound)
    return eventfound

def keyinevent(e, key):
    for field in e:
        if field.lower() == key.lower():
            return True
    return False

def valuefromevent(e, key):
    for field in e:
        if field.lower() == key.lower():
            return e[field]
    return

def valuematcheskey(value, key, constraint, flags):
    
    if not(type(value) == type(constraint)):        #constraint is not the same type as the value, fails
        return False    
    constraintmatch = True
    #key is not a key with special behaviour, default
    prunedflags = []
    for flag in flags:
        if not(flag == 'NOT') and not(flag == 'ANY'):
            prunedflags.append(flag)
    if isinstance(constraint, str):         #is a string
        constraint = constraint.lower()
        value = value.lower()
        if len(prunedflags) == 0:
            if constraint not in value:
                constraintmatch = False
        for flag in flags:
            if flag == 'substring':
                if constraint not in value:
                    constraintmatch = False
            if flag == 'exact':
                if not constraint == value:
                    constraintmatch = False
    elif isinstance(constraint, datetime):  #is a date
        if len(prunedflags) == 0:
            if not constraint == value:
                constraintmatch = False
        for flag in flags:
            if flag == '>=':
                if not constraint >= value:
                    constraintmatch = False
            if flag == '<=':
                if not constraint <= value:
                    constraintmatch = False
            if flag == '>':
                if not constraint > value:
                    constraintmatch = False
            if flag == '<':
                if not constraint < value:
                    constraintmatch = False
            if flag == '==':
                if not constraint == value:
                    constraintmatch = False
    elif isinstance(constraint, int) or isinstance(constraint, float):      #numeric comparison      
        if len(prunedflags) == 0:
            if not(constraint == value):
                constraintmatch = False
        for flag in flags:
            if flag == '>=':
                if not value >= constraint:
                    constraintmatch = False
            if flag == '<=':
                if not value <= constraint:
                    constraintmatch = False
            if flag == '>':
                if not value > constraint:
                    constraintmatch = False
            if flag == '<':
                if not value < constraint:
                    constraintmatch = False
            if flag == '==':
                if not value == constraint:
                    constraintmatch = False
    else:                                                   #unknown datatype, use generic exact match
        if not(constraint == value):
            constraintmatch = False
    return constraintmatch

def removelistsineventfounds(foundevents):
    for foundevent in foundevents:
        for key in foundevent:
            i = 0
            while i < len(foundevent[key]):
                value = foundevent[key][i]
                if isinstance(value, list):
                    if not key in keyswithlisttypevalues:
                        del foundevent[key][i]
                        foundevent[key][i:i] = value
                    else:
                        if not value == [] and isinstance(value[0], list):
                            del foundevent[key][i]
                            foundevent[key][i:i] = value
                i = i + 1
    return foundevents

def evaluate(eventList, queries, connectors, gets, startdepth = 0):
    '''
    queries are a list
    each query is also a list of keyconstraints tuples (see extract)
    constraints can be a fixed value or a wildcard
    constraint wildcards recall values from the currently processing eventfound (see below)
    constraint wildcards are always lists and the [0] must be 'EVENT'
    constraint wildcards [1] is the key of the wildcard
    constraint wildcards [2] is the list position of the wildcard (note: no checks for out of bounds, will crash on invalid values)
    [3] and above are flags and controls
    > 3 is a list, each element of the list is a flag
    
    connectors define how the evaluator reacts to queries, currently implemented AND (default) only, so connectors are not used
    
    eventfoundquerylist is a list of eventfounds returned by the extractor when the searchterm is evaluated
    eventfoundquerylist[0] is the eventfounds returned by the extractor for query[0]
    then the eventfoundquerylist is iterated and each eventfound is applied to the next searchterm to compute wildcards with
    
    eventfounds are a list of dictionary of lists (essentially events with keys pointing to lists of values), with each key being the same key as the data returned by the extractor
    the list position of the value is the same as the searchterm number that returned that data
    eg. eventfound = {'uuid' = [[1], [3], [6]]} would mean that the first searchterm returned an event with a uuid of [1], then the second searchterm using that eventfound returned a uuid of [3] which was added to the uuid of [1], and the third searchterm using that combination returned a uuid of [6]
    
    ()s are handled by recursing the evaluator starting at the brackets; ( starts recursion, ) ends recursion
    returned events are contained as a list, treating the entire () as 1 search term
    connectors after () apply to all elements returned by the recursion
    '''
    foundsets = 0
    foundeventsets = []
    foundgetquerys = []
    orstate = []                 #checked if OR returned something (used in ENDOR to determine pass/fail)
    
    eventfoundquerylist = []
    getsquerylist = []
    eventfoundquerydepth = startdepth           #starts at first searchterm, must not start on a '('
    i = startdepth
    nextdepth = startdepth
    bracketcount = 0
    ornotflag = False
    while True:                     #determine endpoint of range that the evaluator has to process; stops at enough close brackets or end of search
        if len(queries) == i:       #reached end of query
            querynumber = i
            break
        if queries[i][0][0] == "(":
            bracketcount = bracketcount + 1
        if queries[i][0][0] == ")":
            if bracketcount > 0:
                bracketcount = bracketcount - 1
            else:
                querynumber = i
                break
        i = i + 1
    for i in range(0, querynumber):
        eventfoundquerylist.append([])
        getsquerylist.append([])
        orstate.append([])
    #first searchterm cannot contain wildcards
    
    nextgetquerylist = []
    getbracketreturnflag = False
    if not(queries[startdepth][0][0] == "("):                 #1st key is not a '(', not a bracket
        extracted = extract(eventList, queries[startdepth])
    else:                                                       #1st key is a '('
        extracted = []
        if not "SAMEADMISSION" in connectors[startdepth]:
            eventfounds, nextdepth, getfounds = evaluate(eventList, queries, connectors, gets, startdepth + 1)
        else:                           #SAMEADMISSION flag
            eventfounds = []
            nextdepth = startdepth + 1
            getfounds = []
            for eList in chopeventlist(eventList):
                eventfoundtemp, nextdepth, getfoundtemp = evaluate(eList, queries, connectors, gets, startdepth + 1)
                for ef in eventfoundtemp:
                    eventfounds.append(ef)
                for g in getfoundtemp:
                    getfounds.append(g)
        for eventcount in range(0, len(eventfounds)):
            e = copy.deepcopy(eventfounds[eventcount])
            allkeysmatch = True
            for keyconstraint in queries[startdepth]:
                key = keyconstraint[0]
                constraint = copy.deepcopy(keyconstraint[1])            #no wildcards on first searchterm
                flags = copy.deepcopy(keyconstraint[2])
                if key == '' or key == '(' or key == ')':               #empty or bracket keys autopass
                    continue
                if key not in e:                                    #key not present, fails
                    allkeysmatch = False
                    break
                constraintmatch = True
                for value in e[key]:                        #key is present, check if key matches constraint
                    if value == "":                 #OR appends empty strings
                        keyvaluematching = True
                    else:
                        keyvaluematching = valuematcheskey(value, key, constraint, flags)
                    if 'NOT' in flags:
                        keyvaluematching = not keyvaluematching
                    constraintmatch = constraintmatch and keyvaluematching
                    if not constraintmatch:             #a value in the eventfoundlist did not match the key
                        break
                if not constraintmatch:
                    allkeysmatch = False                     #ALL the events in a single eventfound list must match the constraints or this eventfound fails
                    break
                #done, reaching here = this eventfound matches this keyconstraint, got to next keyconstraint
            if allkeysmatch:
                extracted.append(e)
                getbracketreturnflag = True             #disables writing to the GET stack for later portions because it's done here; except for OR propagation
                nextgetquery = []
                nextgetquery.append(getfounds[eventcount])
                nextgetquerylist.append(nextgetquery)
        eventfoundquerydepth = nextdepth
    if len(extracted) == 0:     #nothing found
        if 'OR' in connectors[eventfoundquerydepth]:
            ornotflag = True
        elif 'NOT' in connectors[eventfoundquerydepth]:
            ornotflag = True
        elif 'ONEOF' in connectors[eventfoundquerydepth]:
            ornotflag = True
        else:
            return [], querynumber, []
    else:
        if 'NOT' in connectors[eventfoundquerydepth]:         #NOT first term found something!  FAIL
            return [], querynumber, []

    eventfound = []
    if ('OR' in connectors[eventfoundquerydepth] or 'ONEOF' in connectors[eventfoundquerydepth]) and len(extracted) > 0:            #pass empty if OR, even if found something, needed for ORs in ()
        eventfound.append({})
        nextgetquerylist.insert(0, [])
        orstate[eventfoundquerydepth].append(False)
    for event in extracted:
        if 'OR' in connectors[eventfoundquerydepth]:
            orstate[eventfoundquerydepth].append(True)
        elif 'ONEOF' in connectors[eventfoundquerydepth]:
            orstate[eventfoundquerydepth].append(True)
        else:
            orstate[eventfoundquerydepth].append(False)
        addevent = {}
        for k in event:
            v = event[k]
            addevent[k] = []            #first search term initializes lists, later searchterms only initialize new values and will append null entries until correct list number
            addevent[k].append(v)       #first search term's values applies to 0th position in the value lists
        eventfound.append(addevent)
        if not getbracketreturnflag and 'NOT' not in connectors[eventfoundquerydepth]:
            nextgetquery = []
            if len(gets[eventfoundquerydepth]) > 0:
                for getquery in gets[eventfoundquerydepth]:
                    getkey = getquery[1]
                    if getkey not in addevent:
                        nextgetquery.append(None)
                        #err = KeyNotFoundError("'" + str(eventkey) + "' key to be extracted does not exist in events. ")
                        #raise err
                    else:
                        nextgetquery.append(addevent[getkey])
            nextgetquerylist.append(nextgetquery)
    eventfoundquerylist[eventfoundquerydepth] = eventfound
    getsquerylist[eventfoundquerydepth] = nextgetquerylist

    if eventfoundquerydepth + 1 == querynumber:          #there was only one searchterm!  we are already done!
        foundeventsets = removelistsineventfounds(eventfoundquerylist[eventfoundquerydepth])
        foundgetquerys = getsquerylist[eventfoundquerydepth]
        return foundeventsets, querynumber, foundgetquerys
    
    if debug2:
        log("")
    #print(getsquerylist)
    ###BEGIN MAIN ITERATION LOOP###
    while True:
        #DEBUG
        if debug2:
            log("start: " + str(startdepth) + " ; max: " + str(querynumber) + " ; found: " + str(len(foundeventsets)) + " ; getsfound: " + str(len(foundgetquerys)) + " ; ornotflag: " + str(ornotflag))
            for i in range(startdepth, querynumber):
                debugstr = ""
                try:
                    debugstr = 'query number: ' + str(i) + '; list of events remaining: ' + printuuid(eventfoundquerylist[i]) + '; getcount: ' + str(len(getsquerylist[i]))
                except:
                    pass
                if eventfoundquerydepth == i:
                    debugstr = debugstr + '  <--'
                if not(debugstr == ""):
                    log(debugstr)
                    try:
                        log(str(i) + " " + str(queries[i]) + " " + str(connectors[i]) + " test")
                        log(str(orstate[i]))
                    except:
                        pass
                #print(eventfoundquerylist[i])
            log(str(getsquerylist))
            print(eventfoundquerydepth)
            log("")
        #DEBUG END
        currenteventfoundlist = eventfoundquerylist[eventfoundquerydepth]
        currentgetsquerylist = getsquerylist[eventfoundquerydepth]
        backtracking = False
        if querynumber == eventfoundquerydepth + 1:      #hit end of query list  (queries start at index 0, index at len(query) doesn't exist)
            #anything that is on the last eventfoundquerylist index is whatever survived all the queries; graduated as a valid chain of events that fulfills the query
            #empty the last one, go back down and look for another until that layer is done and proceed with emptying each eventfoundquerydepth until eventfoundquerylist is completely empty
            for finishedevent in currenteventfoundlist:
                foundeventsets.append(finishedevent)
                if debug3:
                    foundsets = foundsets + 1
            if debug3:
                print(foundsets)
            for finishedget in currentgetsquerylist:
                foundgetquerys.append(finishedget)
            currenteventfoundlist = []
            currentgetsquerylist = []
            eventfoundquerylist[eventfoundquerydepth] = []      #empty the last query's eventfound list
            getsquerylist[eventfoundquerydepth] = []
            orstate[eventfoundquerydepth] = []
            backtracking = True
        elif len(currenteventfoundlist) == 0:                   #no more eventfounds for this query, go lower to look for one
            if not ornotflag:                                   #it's not an OR or NOT on the first pass; this will run immediately so it should not affect later search terms
                if eventfoundquerydepth == startdepth:          #we have hit the bottom and it's empty, we are done!  kick out of loop and return foundeventsets
                        if debug2:
                            print("Output: " + printuuid(foundeventsets))
                        foundeventsets = removelistsineventfounds(foundeventsets)
                        return foundeventsets, querynumber, foundgetquerys      #TO DO: handle bracket returns for nested brackets in foundgetquery
                else:
                    orstate[eventfoundquerydepth] = []
                    backtracking = True
            else:
                ornotflag = False
        if backtracking:                                        #decrement and skip brackets; then continue without processing
            eventfoundquerydepth = eventfoundquerydepth - 1
            query = queries[eventfoundquerydepth + 1]
            if query[0][0] == ")":                              #decrement hit a closed bracket
                i = eventfoundquerydepth
                bracketcount = 0
                while True:                                     #to determine start of the closed bracket we just hit
                    if i == startdepth:                         #reached start of query
                        bracketstart = i
                        break
                    if queries[i][0][0] == ")":
                        bracketcount = bracketcount + 1
                    if queries[i][0][0] == "(":
                        if bracketcount > 0:
                            bracketcount = bracketcount - 1
                        else:
                            bracketstart = i - 1
                            break
                    i = i - 1
                eventfoundquerydepth = bracketstart
            continue
        
        #this query list is not empty and there is a new query for it; pull the event on the top and process the query in its context
        #process a currenteventfound from the list with the next query for it
        query = queries[eventfoundquerydepth + 1]
        if len(currenteventfoundlist) > 0:
            currenteventfound = currenteventfoundlist.pop(0)
        else:                                           #list is empty, only generated by NOT and OR in first term
            currenteventfound = {}                      #should raise a KeyNotFoundError if the 2nd term has wildcards
        if len(currentgetsquerylist) > 0:
            currentgetsquery = currentgetsquerylist.pop(0)
        else:
            currentgetsquery = []
        if len(orstate[eventfoundquerydepth]) > 0:
            currentorstate = orstate[eventfoundquerydepth].pop(0)
        else:
            currentorstate = False
        buildquery = []                                 #collects wildcard-processed keyconstraints into a defined query
        for keyconstraint in query:                     #check each keyconstraint in the query and see if it has wildcards that need processing
            key = keyconstraint[0]
            assert not(key == ")")                      #key should never be ')'; something has gone wrong if this triggers, will have buggy behaviour if ignored
            if key == "(" or key == ")":                #is a bracket term, ignore this key but process the rest
                continue
            constraint = copy.deepcopy(keyconstraint[1])
            flags = copy.deepcopy(keyconstraint[2])
            if isinstance(constraint, list) and constraint[0] == 'EVENT':       #is ASPREVIOUS wildcard
                eventkey = constraint[1]
                eventquerydepth = constraint[2]
                if eventkey not in currenteventfound:           #wildcard is based on a key that previous events don't have
                    err = KeyNotFoundError("Wildcard key '" + str(eventkey) + "' does not exist in previous events. ")
                    raise err
                if eventquerydepth < 0:
                    eventquerydepth = len(currenteventfound[eventkey]) + eventquerydepth
                if len(constraint) == 4:
                    eventflags = constraint[3]
                else:
                    eventflags = []
                isrange = False
                for flag in eventflags:
                    if isinstance(flag, list) and flag[0] == "range":   #range flags denote a range of past events on which the wildcard will operate; treats that range as a bracket return
                        isrange = flag[1]
                if (eventkey in keyswithlisttypevalues and len(currenteventfound[eventkey]) > eventquerydepth and not(isinstance(currenteventfound[eventkey][eventquerydepth][0], list)) and (isrange is False)) or (eventkey not in keyswithlisttypevalues and not isinstance(currenteventfound[eventkey][eventquerydepth], list) and (isrange is False)):      #target eventquerydepth to base this wildcard on is a query, not a bracket return and not having a range flag; special case coding for 'uuid' eventkeys as those are lists
                    eventconstraint = copy.deepcopy(currenteventfound[eventkey][eventquerydepth])
                    if len(constraint) == 4:        #check for offset flags
                        for flag in eventflags:
                            if isinstance(flag, list) and flag[0] == "OFFSET":
                                if flag[1] == 'N':
                                    offset = int(flag[3])
                                    if flag[2] == '+':
                                        eventconstraint = eventconstraint + offset
                                    elif flag[2] == '-':
                                        eventconstraint = eventconstraint - offset
                                elif flag[1] == 'T':
                                    offset = converttimedelta(flag[3])
                                    if flag[2] == '+':
                                        eventconstraint = eventconstraint + offset
                                    elif flag[2] == '-':
                                        eventconstraint = eventconstraint - offset
                else:                                                           #is a bracket return
                    currentkey = currenteventfound[eventkey][eventquerydepth]
                    if not (isrange is False):             #Range flag overrides the given eventquery depth
                        currentkey = []
                        eventconstraint = []
                        for r in isrange:
                            if r < 0:
                                r = len(currenteventfound[eventkey]) + r
                            currentkey.append(copy.deepcopy(currenteventfound[eventkey][r]))
                            eventconstraint.append(copy.deepcopy(currenteventfound[eventkey][r]))
                    else:
                        eventconstraint = copy.deepcopy(currenteventfound[eventkey][eventquerydepth][len(currenteventfound[eventkey][eventquerydepth]) - 1])    #default is the last entry
                    if len(constraint) == 4:                            #check for wildcard flags; 'earliest' and 'latest' flags only work for starttime and endtime wildcards
                        for flag in eventflags:
                            if flag == 'latest' and (eventkey == 'starttime' or eventkey == 'endtime'):
                                latesttime = 0
                                for time in currentkey:
                                    if time == "":
                                        continue
                                    if latesttime == 0:
                                        latesttime = time
                                        continue
                                    if latesttime < time:
                                        latesttime = time
                                eventconstraint = latesttime
                            if flag == 'earliest' and (eventkey == 'starttime' or eventkey == 'endtime'):
                                earliesttime = 0
                                for time in currentkey:
                                    if time == "":
                                        continue
                                    if earliesttime == 0:
                                        earliesttime = time
                                        continue
                                    if earliesttime > time:
                                        earliesttime = time
                                eventconstraint = earliesttime
                            if flag == 'rangelatest' and (eventkey == 'starttime' or eventkey == 'endtime'):        #used for range; gives earliest for a range but latest for brackets inside the range; behaves like earliest if used on non-range
                                earliesttime = 0
                                for time in currentkey:
                                    if time == "":
                                        continue
                                    if isinstance(time, list):
                                        latestt = 0
                                        for t in time:
                                            if t == "":
                                                continue
                                            if latestt == 0:
                                                latestt = t
                                                continue
                                            if latestt > t:
                                                latestt = t
                                        time = latestt
                                    if earliesttime == 0:
                                        earliesttime = time
                                        continue
                                    if earliesttime < time:
                                        earliesttime = time
                                eventconstraint = earliesttime
                            if flag == 'rangeearliest' and (eventkey == 'starttime' or eventkey == 'endtime'):
                                latesttime = 0
                                for time in currentkey:
                                    if time == "":
                                        continue
                                    if isinstance(time, list):
                                        earliestt = 0
                                        for t in time:
                                            if t == "":
                                                continue
                                            if earliestt == 0:
                                                earliestt = t
                                                continue
                                            if earliestt < t:
                                                earliestt = t
                                        time = earliestt
                                    if latesttime == 0:
                                        latesttime = time
                                        continue
                                    if latesttime > time:
                                        latesttime = time
                                eventconstraint = latesttime
                            if isinstance(flag, list) and flag[0] == "OFFSET":
                                if flag[1] == 'N':
                                    offset = int(flag[3])
                                    if flag[2] == '+':
                                        eventconstraint = eventconstraint + offset
                                    elif flag[2] == '-':
                                        eventconstraint = eventconstraint - offset
                                elif flag[1] == 'T':
                                    offset = converttimedelta(flag[3])
                                    if flag[2] == '+':
                                        eventconstraint = eventconstraint + offset
                                    elif flag[2] == '-':
                                        eventconstraint = eventconstraint - offset
                            if flag == 'any':                           #the ANY extractor flag means the constraint is a bracket return and the value has to match only one of the constraints to pass
                                flags.append('ANY')
                                eventconstraint = copy.deepcopy(currentkey)
                buildkeyconstraint = (key, eventconstraint, flags)
                buildquery.append( buildkeyconstraint )
            else:
                buildquery.append( copy.deepcopy(keyconstraint) )
        
        if debug2:
            log("buildquery: " + str(buildquery))
        
        nextgetquerylist = []
        getbracketreturnflag = False
        #keyconstraints processed, get output and check
        if not(query[0][0] == "("):                 #1st key is not a '(', not a bracket
            extracted = extract(eventList, buildquery)
            nextdepth = eventfoundquerydepth + 1
        else:                                       #'(' bracket start, recurse, collect result and parse result using remaining keyconstraints
            extracted = []
            if not "SAMEADMISSION" in connectors[eventfoundquerydepth + 1]:
                eventfounds, nextdepth, getfounds = evaluate(eventList, queries, connectors, gets, eventfoundquerydepth + 2)
            else:                           #SAMEADMISSION flag
                eventfounds = []
                nextdepth = eventfoundquerydepth + 1
                getfounds = []
                for eList in chopeventlist(eventList):
                    eventfoundtemp, nextdepth, getfoundtemp = evaluate(eList, queries, connectors, gets, eventfoundquerydepth + 2)
                    for ef in eventfoundtemp:
                        eventfounds.append(ef)
                    for g in getfoundtemp:
                        getfounds.append(g)
            for eventcount in range(0, len(eventfounds)):
                e = eventfounds[eventcount]
                allkeysmatch = True
                for keyconstraint in buildquery:
                    key = keyconstraint[0]
                    constraint = copy.deepcopy(keyconstraint[1])            #should not be wildcards anymore
                    flags = copy.deepcopy(keyconstraint[2])
                    #print(key, ",", constraint, ",", flags)
                    if key == '' or key == '(' or key == ')':               #empty or bracket keys autopass
                        continue
                    if key not in e:                                    #key not present, fails
                        allkeysmatch = False
                        break
                    constraintmatch = True
                    for value in e[key]:                        #key is present, check if key matches constraint
                        #print(value)
                        if value == "":                 #OR appends empty strings
                            keyvaluematching = (not 'NOT' in flags)
                        else:
                            keyvaluematching = valuematcheskey(value, key, constraint, flags)
                        if 'NOT' in flags:
                            keyvaluematching = not keyvaluematching
                        constraintmatch = constraintmatch and keyvaluematching
                        if not constraintmatch:             #a value in the eventfoundlist did not match the key
                            break
                    if not constraintmatch:                     #ALL the events must match the constraints or this eventfound fails
                        allkeysmatch = False
                        #print("not all keys match", key, ",", constraint, ",", flags)
                        break
                    #print("all keys match")
                    #done, reaching here = this eventfound matches this key
                if allkeysmatch:
                    extracted.append(e)
                    getbracketreturnflag = True             #disables writing to the GET stack for later portions because it's done here; except for OR propagation
                    nextgetquery = copy.deepcopy(currentgetsquery)
                    nextgetquery.append(getfounds[eventcount])
                    nextgetquerylist.append(nextgetquery)
        
        #got the returns, check for connector flags (AND/OR/NOT)
        #OR checks at the target write point instead of simply next connector to support this: ") OR" will close brackets then OR
        if connectors[eventfoundquerydepth + 1][0] == 'AND' and not 'OR' in connectors[nextdepth] and not 'ONEOF' in connectors[nextdepth]:       #default connector flag, adds to next list
            nexteventfoundlist = []
            if 'ANYNUMBEROF' in connectors[eventfoundquerydepth + 1]:          #anynumberof flag, assumes return is not from a bracket
                nexteventfound = copy.deepcopy(currenteventfound)
                for event in extracted:                                 #initialize keys
                    for k in event:
                        if k not in currenteventfound:
                            nexteventfound[k] = []
                            for i in range(0, getreturncountatdepth(queries, eventfoundquerydepth)):        #keys not previously present get filled with empty strings up until the expected number of returns
                                nexteventfound[k].append('')
                for k in nexteventfound:
                    keycollectvalues = []
                    for event in extracted:
                        if keyinevent(event, k):
                            keycollectvalues.append(event[k])
                        else:
                            keycollectvalues.append("")
                    nexteventfound[k].append(keycollectvalues)
                nexteventfoundlist.append(nexteventfound)
                orstate[nextdepth].append(False)
                if not getbracketreturnflag:                            #blocks double writing from bracket returns
                    nextgetquery = copy.deepcopy(currentgetsquery)
                    if len(gets[eventfoundquerydepth + 1]) > 0:         #if there are GETs, get them
                        for event in extracted:                                 #collect all events' gets and make one array for ANYNUMBEROF
                            nextget = []
                            for getkey in gets[eventfoundquerydepth + 1]:
                                if getkey[1] in event:
                                    nextget.append(event[getkey[1]])
                                else:
                                    nextget.append(None)
                            nextgetquery.append(nextget)
                    else:
                        nextgetquery.append([])
                    nextgetquerylist.append(nextgetquery)
            else:                                                     #default
                for event in extracted:
                    orstate[nextdepth].append(False)                   #if this connector is not OR, always set to false
                    nexteventfound = copy.deepcopy(currenteventfound)
                    for k in event:
                        v = event[k]
                        if k in currenteventfound:
                            nexteventfound[k].append(v)                 #brackets get handled as list objects
                        else:
                            nexteventfound[k] = []
                            for i in range(0, getreturncountatdepth(queries, eventfoundquerydepth)):        #keys not previously present get filled with empty strings up until the current query number
                                nexteventfound[k].append('')
                            nexteventfound[k].append(v)
                    nexteventfoundlist.append(nexteventfound)
                    if not getbracketreturnflag:                            #blocks double writing from bracket returns
                        nextgetquery = copy.deepcopy(currentgetsquery)
                        if len(gets[eventfoundquerydepth + 1]) > 0:         #if there are GETs, get them
                            nextget = []
                            for getkey in gets[eventfoundquerydepth + 1]:
                                if getkey[1] in event:
                                    nextget.append(event[getkey[1]])
                                else:
                                    nextget.append(None)
                            nextgetquery.append(nextget)
                        else:
                            nextgetquery.append([])
                        nextgetquerylist.append(nextgetquery)
            eventfoundquerylist[nextdepth] = nexteventfoundlist
            getsquerylist[nextdepth] = nextgetquerylist
        if connectors[eventfoundquerydepth + 1][0] == 'NOT':       #NOT connectors only pass if they find nothing
            #print("test")
            if len(extracted) == 0:                         #found nothing, copy currenteventfound as next eventfoundlist of size 1
                nexteventfoundlist = []
                nexteventfound = copy.deepcopy(currenteventfound)
                nexteventfoundlist.append(nexteventfound)
                #eventfoundquerylist[eventfoundquerydepth + 1] = nexteventfoundlist
                eventfoundquerylist[nextdepth] = nexteventfoundlist
                nextgetquery = copy.deepcopy(currentgetsquery)
                nextgetquerylist.append(nextgetquery)
                getsquerylist[nextdepth] = nextgetquerylist
                orstate[nextdepth].append(False)                #a NOT found nothing
            else:                                           #found something, so fail it
                nextgetquerylist = []                       #empty out the getlist and propagate
                getsquerylist[nextdepth] = nextgetquerylist
        if connectors[eventfoundquerydepth + 1][0] == 'ENDOR' or 'OR' in connectors[nextdepth] or 'ONEOF' in connectors[nextdepth]:
            #OR connectors pass even if nothing returns; they add to the returns if something is found
            #ENDOR connectors pass only if either they or the previous OR added something; they add to the returns if something is founds; ENDOR is always found in the first slot
            #ONEOF connectors will append eventfounds if orstate is false, appends only empty otherwise
            if len(extracted) == 0:                         #same as NOT
                if currentorstate or 'OR' in connectors[nextdepth] or 'ONEOF' in connectors[nextdepth]:     #if found something already or is first term (or chained ORs); otherwise, fail
                    orstate[nextdepth].append(currentorstate)      #propagate ORstate (if already found something, keep it True)
                    nexteventfoundlist = []
                    nexteventfound = copy.deepcopy(currenteventfound)
                    nexteventfoundlist.append(nexteventfound)
                    #eventfoundquerylist[eventfoundquerydepth + 1] = nexteventfoundlist
                    eventfoundquerylist[nextdepth] = nexteventfoundlist
                    nextgetquery = copy.deepcopy(currentgetsquery)
                    nextgetquerylist.insert(0, nextgetquery)
                    getsquerylist[nextdepth] = nextgetquerylist
                else:                                           #did not find anything in ENDOR
                    nextgetquerylist = []                       #empty out the getlist and propagate
                    getsquerylist[nextdepth] = nextgetquerylist
            else:                                           #same as AND
                nexteventfoundlist = []
                if 'ONEOF' in connectors[nextdepth] or 'OR' in connectors[nextdepth] or (connectors[nextdepth][0] == 'ENDOR' and currentorstate):
                    nexteventfound = copy.deepcopy(currenteventfound)           #append nothing to address OR CONNECTOR; do not do for the last OR unless already found something
                    nexteventfoundlist.append(nexteventfound)
                    nextgetquery = copy.deepcopy(currentgetsquery)
                    nextgetquerylist.insert(0, nextgetquery)                    #insert at front to make the order of the GET stack match the EVENTFOUND stack when considering bracket returns
                    orstate[nextdepth].append(currentorstate)                #propagate orstate
                if 'ANYNUMBEROF' in connectors[eventfoundquerydepth + 1]:          #anynumberof flag, assumes return is not from a bracket
                    nexteventfound = copy.deepcopy(currenteventfound)
                    for event in extracted:                                 #initialize keys
                        for k in event:
                            v = event[k]
                            if k not in currenteventfound:
                                nexteventfound[k] = []
                                for i in range(0, getreturncountatdepth(queries, eventfoundquerydepth)):        #keys not previously present get filled with empty strings up until the current query number
                                    nexteventfound[k].append('')
                    for k in nexteventfound:
                        keycollectvalues = []
                        for event in extracted:
                            if keyinevent(event, k):
                                keycollectvalues.append(event[k])
                            else:
                                keycollectvalues.append("")
                        nexteventfound[k].append(keycollectvalues)
                    nexteventfoundlist.append(nexteventfound)
                    orstate[nextdepth].append(True)                #Found something!  ORstate set
                    if not getbracketreturnflag:                            #blocks double writing from bracket returns
                        nextgetquery = copy.deepcopy(currentgetsquery)
                        if len(gets[eventfoundquerydepth + 1]) > 0:         #if there are GETs, get them
                            for event in extracted:                                 #collect all events' gets and make one array for ANYNUMBEROF
                                nextget = []
                                for getkey in gets[eventfoundquerydepth + 1]:
                                    if getkey[1] in event:
                                        nextget.append(event[getkey[1]])
                                    else:
                                        nextget.append(None)
                                nextgetquery.append(nextget)
                        else:
                            nextgetquery.append([])
                        nextgetquerylist.append(nextgetquery)
                elif 'ONEOF' not in connectors[eventfoundquerydepth] or ('ONEOF' in connectors[eventfoundquerydepth] and not currentorstate):               #default
                    for event in extracted:
                        orstate[nextdepth].append(True)                #Found something!  ORstate set
                        nexteventfound = copy.deepcopy(currenteventfound)
                        for k in event:
                            v = event[k]
                            if k in currenteventfound:
                                nexteventfound[k].append(v)                 #brackets get handled as list objects
                            else:
                                nexteventfound[k] = []
                                for i in range(0, getreturncountatdepth(queries, eventfoundquerydepth)):        #keys not previously present get filled with empty strings up until the current query number
                                    nexteventfound[k].append('')
                                nexteventfound[k].append(v)
                        nexteventfoundlist.append(nexteventfound)
                        if not getbracketreturnflag:                            #blocks double writing from bracket returns
                            nextgetquery = copy.deepcopy(currentgetsquery)
                            if len(gets[eventfoundquerydepth + 1]) > 0:         #if there are GETs, get them
                                nextget = []
                                for getkey in gets[eventfoundquerydepth + 1]:
                                    if getkey[1] in event:
                                        nextget.append(event[getkey[1]])
                                    else:
                                        nextget.append(None)
                                nextgetquery.append(nextget)
                            else:
                                nextgetquery.append([])
                            nextgetquerylist.append(nextgetquery)
                eventfoundquerylist[nextdepth] = nexteventfoundlist
                getsquerylist[nextdepth] = nextgetquerylist
        eventfoundquerydepth = nextdepth         #follow the new list upwards

def translate(userquery):
    '''
    turns a user entered query into a list of evaluate-able queries and connectors
    user queries are separated into words delimited by white space
    operational words like NOT and FOLLOWEDBY must be one word and in all capitals
    search strings like 'intracranial' must be all lower-case, underscores will be replaced with ' '
    '''
    #constants
    connectorwords = ["AND", "FOLLOWEDBY", "STRICTLYFOLLOWEDBY", "PRECEDEDBY", "STRICTLYPRECEDEDBY", "BETWEEN", "STRICTLYBETWEEN", "ENDSEARCH"]
    searchwords = ["NOT", "ANYNUMBEROF", "OR", "ONEOF"]
    brackets = ["(", ")"]
    
    #initial parser
    #chops user input into words and searchterms / connectors for later translation
    #print(userquery)
    words = userquery.split()
    for i in range(0, len(words)):
        words[i] = words[i].replace('_', ' ')
    userquerylist = []
    connectorlist = []
    searchtermsplitindex = -1
    i = 0
    while i < len(words):
        word = words[i]
        if word[:1] in brackets and not(word in brackets):
            words[i:i] = [word[:1]]
            words[i + 1] = word[1:]
            continue
        if word[-1:] in brackets and not(word in brackets):
            words[i + 1: i + 1] = [word[-1:]]
            words[i] = word[:-1]
            continue
        i = i + 1
    i = 0
    while i < len(words):
        word = words[i]
        querywords = []
        if word.isupper() or word in brackets:
            if word in connectorwords:                          #found a connector word, everything from the last connector to this connector is one search term
                querywords = words[searchtermsplitindex + 1: i]
                if words[i-1] == ")":
                    userquerylist.append([")"])
                else:
                    userquerylist.append(querywords)
                connectorlist.append(word)
                searchtermsplitindex = i
            if word == "(":
                querywords = words[searchtermsplitindex + 1: i]
                querywords.append("(")
                if words[i-1] == ")":
                    userquerylist.append([")"])
                else:
                    userquerylist.append(querywords)
                connectorlist.append(word)
                searchtermsplitindex = i
                word = words[i + 1]
                if word == "SAMEADMISSION":
                    i = i + 1
                    connectorlist.append(word)          #SAMEADMISSION violates synchronized count of userquerylist and connectorlist, this extra entry is removed later
                    searchtermsplitindex = i
            if word == ")":
                querywords = words[searchtermsplitindex + 1: i]
                if words[i-1] == ")":
                    userquerylist.append([")"])
                else:
                    userquerylist.append(querywords)
                connectorlist.append(word)
                searchtermsplitindex = i
            if word in searchwords:                 #found a search word, accumulate all searchwords until a key or a connector;
                searchwordstart = i
                searchwordend = i + 1
                while words[searchwordend] in searchwords:
                    searchwordend = searchwordend + 1
                if words[searchwordend] in connectorwords:              #hit a connector
                    for count in range(0, searchwordend - searchwordstart):
                        words[i] = words[i] + " " + words[i + 1]
                        del words[i + 1]
                    if words[i - 1] == ")":
                        userquerylist.append([")"])
                    else:
                        querywords = words[searchtermsplitindex + 1: i]
                        userquerylist.append(querywords)
                    connectorlist.append(words[i])
                    #print(searchtermsplitindex, words, querywords)
                    searchtermsplitindex = i
                elif words[searchwordend] == "(":                         #hit open bracket
                    for count in range(0, searchwordend - searchwordstart - 1):
                        words[i] = words[i] + " " + words[i + 1]
                        del words[i + 1]
                    words[i] = words[i] + " AND"
                    if words[i - 1] == ")":
                        userquerylist.append([")"])
                    else:
                        querywords = words[searchtermsplitindex + 1: i]
                        userquerylist.append(querywords)
                    connectorlist.append(words[i])
                    #print(searchtermsplitindex, words, querywords)
                    searchtermsplitindex = i
                else:                                                   #hit a key
                    for count in range(0, searchwordend - searchwordstart):
                        words[i] = words[i] + " " + words[i + 1]
                        del words[i + 1]
        i = i + 1
    
    if debug:
        print(userquerylist, connectorlist)
    
    #translator
    #turns each userquerylist into a searchterm usable by evaluator
    querylist = []
    userquery = userquerylist[0]                #process first query; first query cannot be a NOT
    query = parsekeyconstraint(userquery)
    connectors = []
    connectors.append(['AND'])
    querylist.append(query)
    for queryindex in range(1, len(userquerylist)):
        userquery = userquerylist[queryindex]
        connector = connectorlist[queryindex - 1]
        connector = connector.split()
        query = parsekeyconstraint(userquery)
        buildconnector = []
        if "NOT" in connector:
            buildconnector.append('NOT')
        elif "OR" in connector:
            connectors[len(connectors) - 1].append('OR')
            buildconnector.append('ENDOR')
        elif "ONEOF" in connector:
            connectors[len(connectors) - 1].append('ONEOF')
            buildconnector.append('ENDOR')
        else:
            buildconnector.append('AND')
        if "ANYNUMBEROF" in connector:
            buildconnector.append('ANYNUMBEROF')
        connectors.append(buildconnector)
        if "FOLLOWEDBY" in connector and "NOT" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["earliest"]], ['<=']])           #not after earliest time in previous return if []; interpreted strictly for the rest
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            querylist.append(query)
            continue                #NOT terms do not generate a dictlist entry; do not increment querynumber
        if "STRICTLYFOLLOWEDBY" in connector and "NOT" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["earliest"]], ['<']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            querylist.append(query)
            continue
        if "BETWEEN" in connector and "NOT" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["rangelatest", ["range", [-1, -2]]]], ['>=']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            query.append(['starttime', ['EVENT', 'starttime', -2, ["rangeearliest", ["range", [-1, -2]]]], ['<=']])
            query.append(['uuid', ['EVENT', 'uuid', -2, ["any"]], ['NOT']])
            querylist.append(query)
            if debug:
                print("TEST")
            continue
        if "STRICTLYBETWEEN" in connector and "NOT" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["rangelatest", ["range", [-1, -2]]]], ['>']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            query.append(['starttime', ['EVENT', 'starttime', -2, ["rangeearliest", ["range", [-1, -2]]]], ['<']])
            query.append(['uuid', ['EVENT', 'uuid', -2, ["any"]], ['NOT']])
            querylist.append(query)
            continue
        if "AND" in connector and "NOT" in connector:
            querylist.append(query)
            continue
        if "PRECEDEDBY" in connector and "NOT" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["latest"]], ['>=']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            querylist.append(query)
            continue
        if "STRICTLYPRECEDEDBY" in connector and "NOT" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["latest"]], ['>']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            querylist.append(query)
            continue
        if "(" in connector:
            if connectorlist[queryindex] == "SAMEADMISSION":
                connectorlist.pop(queryindex)           #remove connectorlist extra entry for SAMEADMISSION
                connectors[len(connectors) - 2].append("SAMEADMISSION")         #HACK: buildconnector cannot be used here so have to edit connectors list directly
        if ")" in connector:
            pass
        if "OR" in connector:
            pass
        if "BETWEEN" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["rangelatest", ["range", [-1, -2]]]], ['>=']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            query.append(['starttime', ['EVENT', 'starttime', -2, ["rangeearliest", ["range", [-1, -2]]]], ['<=']])
            query.append(['uuid', ['EVENT', 'uuid', -2, ["any"]], ['NOT']])
        if "STRICTLYBETWEEN" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["rangelatest", ["range", [-1, -2]]]], ['>']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
            query.append(['starttime', ['EVENT', 'starttime', -2, ["rangeearliest", ["range", [-1, -2]]]], ['<']])
            query.append(['uuid', ['EVENT', 'uuid', -2, ["any"]], ['NOT']])
        if "PRECEDEDBY" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["earliest"]], ['>=']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
        if "STRICTLYPRECEDEDBY" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["earliest"]], ['>']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
        if "FOLLOWEDBY" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["latest"]], ['<=']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
        if "STRICTLYFOLLOWEDBY" in connector:
            query.append(['starttime', ['EVENT', 'starttime', -1, ["latest"]], ['<']])
            query.append(['uuid', ['EVENT', 'uuid', -1, ["any"]], ['NOT']])
        querylist.append(query)
    
    #Remove preceding empty queries generated by beginning a statement with "NOT ("
    if len(querylist[0]) == 0:
        querylist.pop(0)
        connectors.pop(0)
    
    #Propagate NOT flag for ( to the corresponding ); this allows NOT ( to work if the statement begins with it
    i = 0
    for i in range(0, len(querylist)):
        query = querylist[i]
        if query[0][0] == '(' and 'NOT' in connectors[i]:
            currentindex = i + 1
            bracketcount = 1
            while True:
                query2 = querylist[currentindex]
                if query2[0][0] == '(':
                    bracketcount = bracketcount + 1
                if query2[0][0] == ')':
                    bracketcount = bracketcount - 1
                    if bracketcount == 0:
                        connectors[currentindex][0] = 'NOT'
                        break
                currentindex = currentindex + 1
    
    #Process GET statements
    gets = []
    for i in range(0, len(querylist)):
        query = querylist[i]
        newquery = []
        getstatements = []
        for keyconstraint in query:
            if keyconstraint[0] == "get":
                getstatements.append(keyconstraint)
            else:
                newquery.append(keyconstraint)
        querylist[i] = newquery
        gets.append(getstatements)
    
    if debug:       #DEBUG
        print("query list:")
        for i in range(0, len(querylist)):
            try:
                print(querylist[i], connectors[i], gets[i])
            except:
                pass
    return querylist, connectors, gets

def parsekeyconstraint(userquery):
    notkeys = ["NUMERIC", "DATETIME", "ASPREVIOUS"]                           #some modifiers that are not keys
    query = []
    i = 0
    while i < len(userquery):
        searchterm = []
        word = userquery[i]
        if word == "(" or word == ")":
            searchterm.append(word)
            searchterm.append("")
            searchterm.append([])
            query.append(searchterm)
            i = i + 1
            continue
        flags = []
        if word[:4] == 'NOT ':
            word = word[4:]
            flags.append('NOT')
        ASPREVIOUSinword = False
        if len(word) >= 10:
            if word[:10] == "ASPREVIOUS":
                ASPREVIOUSinword = True
        if word.isupper() and word not in notkeys and not ASPREVIOUSinword and not word[:6] == "OFFSET":              #found key, begin new searchterm
            searchterm.append(word.lower())
            i = i + 1
            if not (i == len(userquery)):
                word = userquery[i]
        else:                                       #did not start with key; search against all keys using ANY keyword
            searchterm.append("ANY")
        constrainttype = ""
        if word == "NUMERIC":                       #post-keys get flags
            i = i + 1
            word = userquery[i]
            while True:
                flag = numericflag(word)
                if flag == 'not':
                    break
                i = i + 1
                word = userquery[i]
                flags.append(flag)
            constrainttype = "NUMERIC"
        elif word == "DATETIME":
            i = i + 1
            word = userquery[i]
            while True:
                flag = timeflag(word)
                if flag == 'not':
                    break
                i = i + 1
                word = userquery[i]
                flags.append(flag)
            constrainttype = "DATETIME"
        if len(word) >= 10 and word[:10] == "ASPREVIOUS":       #special ASPREVIOUS constraint; expects a target key or flags + key after this
            constraint = []
            constraint.append("EVENT")
            i = i + 1
            noflag = False
            offset = []
            while True:                                         #ASPREVIOUS accepts all flags
                noflag = False
                nooffsetflag = False
                flag = numericflag(userquery[i])
                if flag == 'not':
                    flag = timeflag(userquery[i])
                    if flag == 'not':
                        noflag = True
                oflag = offsetflag(userquery[i])
                if oflag == 'not':
                    nooffsetflag = True
                if noflag and nooffsetflag:
                    break
                i = i + 1
                if not noflag:
                    flags.append(flag)
                if not nooffsetflag:
                    offset.append(oflag)
            constraint.append(userquery[i].lower())
            if word[10:] == "":                                 #ASPREVIOUS defaults to previous position
                constraint.append(-1)
            else:                                               #ASPREVIOUSx uses data from event at given searchterm, negative numbers are relative to current search term
                constraint.append(int(word[10:]))
            constraint.append(offset)
            constrainttype = "ASPREVIOUS"
        if constrainttype == "NUMERIC":                       #parse constraints
            word = convertnum(userquery[i])
        elif constrainttype == "DATETIME":
            word = converttime(userquery[i])
        elif constrainttype == "ASPREVIOUS":
            word = constraint
        else:
            word = word.lower()
        searchterm.append(word)                     #constraint
        searchterm.append(flags)
        query.append(searchterm)
        i = i + 1
    return query

def convertnum(num):
    try:
        return int(num)
    except ValueError:
        return float(num)

def numericflag(word):
    if word == "GREATERTHAN":
        return '>'
    if word == "LESSTHAN":
        return '<'
    if word == "GREATERTHANEQUALS":
        return '>='
    if word == "LESSTHANEQUALS":
        return '<='
    if word == "EQUALS":
        return '=='
    return 'not'

def timeflag(word):
    if word == "BEFORE":
        return '>='
    if word == "AFTER":
        return '<='
    if word == "STRICTLYBEFORE":
        return '>'
    if word == "STRICTLYAFTER":
        return '<'
    if word == "EQUALS":
        return '=='
    return 'not'

def offsetflag(word):       #OFFSET[N/T][+/-][integer/time]     time follows converttime's format
    if word[:6] == "OFFSET" and len(word) > 8:
        return ['OFFSET', word[6:7], word[7:8], word[8:]]
    return 'not'

def converttime(time):              #YYYY_MM_DD_HH_MM_SS
    timesteps = time.split()
    dt = []
    for timestep in timesteps:
        dt.append(int(timestep))
    return datetime(*dt)

def converttimedelta(time):              #DD_HH_MM_SS
    length = len(time)
    timesteps = time.split()
    dt = []
    for timestep in timesteps:
        dt.append(int(timestep))
    return timedelta(*dt)

def printuuid(eventfoundset):
    restr = ""
    for e in eventfoundset:
        try:
            restr = restr + str(e['uuid']) + " "
        except:
            restr = restr + " none "
    return restr

def getbracketcountatdepth(querylist, depth):
    count = 0
    for i in range(0, depth + 1):
        query = querylist[i]
        if query[0][0] == '(' or query[0][0] == ')':
            count = count + 1
    return count

def getreturncountatdepth(querylist, depth):
    count = 0
    bracketcount = 0
    while depth >= 0:
        query = querylist[depth]
        if query[0][0] == ')':
            bracketcount = bracketcount + 1
        if query[0][0] == '(':
            bracketcount = bracketcount - 1
        if bracketcount < 0:
            break
        if bracketcount == 0:
            count = count + 1
        depth = depth - 1
    return count
    
def chopeventlist(eventList):       #assumes eventList is sorted by starttime
    inadmission = False
    eventcount = len(eventList)
    choppedeventlist = []
    i = 0
    while True:
        e = eventList[i]
        key = 'description'
        constraint = 'startadmission'
        if not inadmission and keyinevent(e, key):
            if constraint in valuefromevent(e, key):        #found startadmission
                inadmission = True
                admissionstarttime = valuefromevent(e, 'starttime')
                admissionstartindex = i
                while True:                                 #backtrace to first event sharing same time as startadmission, excluding 
                    if not(admissionstartindex == 0):
                        if valuefromevent(eventList[admissionstartindex - 1], 'starttime') == admissionstarttime:
                            admissionstartindex = admissionstartindex - 1
                        else:
                            break
                    else:
                        break
                eventlistcol = []
        if inadmission:
            eventlistcol.append(e)
            key = 'description'
            constraint = 'endadmission'
            if keyinevent(e, key):
                if constraint in valuefromevent(e, key):        #found endadmission
                    inadmission = False
                    admissionendtime = valuefromevent(e, 'starttime')
                    admissionendindex = i
                    while True:
                        if admissionendindex < eventcount - 1:
                            if valuefromevent(eventList[admissionendindex + 1], 'starttime') == admissionendtime:
                                eventlistcol.append(eventList[admissionendindex + 1])
                                admissionendindex = admissionendindex + 1
                            else:
                                break
                        else:
                            break
                    i = admissionendindex
                    choppedeventlist.append(eventlistcol)
        i = i + 1
        if i == eventcount:
            break
    return choppedeventlist

def log(text):
    logfile.write(str(text))
    logfile.write("\n")
    print(text)
    
if __name__ == '__main__':
    logfile = open("eventsearchlog.txt", "w")
    debug = False
    debug2 = False
    debug3 = False
    debug4 = False
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0)},
    {'uuid':[2], 'code': u'G93.2 ', 'endtime': datetime(2011, 5, 28, 18, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2011, 5, 28, 18, 9)},  
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2012, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2012, 5, 28, 18, 10)},   
    
    {'uuid':[5], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 18, 9)}, 
    {'uuid':[7], 'code': u'R94.5 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'abnormal results of liver function studies ', 'starttime': datetime(2014, 5, 28, 18, 9)}, 
    {'uuid':[8], 'code': u'Z86.43 ', 'endtime': datetime(2015, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2015, 5, 28, 18, 9)}, 
    {'uuid':[9], 'endtime': datetime(2016, 5, 28, 20, 9), 'type': 'pathology ', 'result':15210, 'test':'ferritin', 'starttime': datetime(2016, 5, 28, 20, 9)}, 
    {'uuid':[10], 'code': u'Z86.43 ', 'endtime': datetime(2017, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2017, 5, 28, 18, 9)}, 
    {'uuid':[11], 'endtime': datetime(2018, 5, 28, 20, 9, 1), 'type': 'admin ', 'description': 'endadmission ', 'starttime': datetime(2018, 5, 28, 20, 9, 1)},
    {'uuid':[12], 'code': u'G93.2 ', 'endtime': datetime(2019, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2019, 5, 28, 18, 10)}]
    
    log("EXTRACTOR unit tests")
    test = extract(eventList, [('starttime', datetime(2012, 5, 28, 18, 10), ['<='])])
    log(str(len(test)) + " unit test 1 end\n")
    assert len(test) == 8
    
    query = [ ('description', 'intracranial ', ['NOT']),
    ('starttime', datetime(2012, 5, 28, 18, 10), ['<='])
    ]
    test = extract(eventList, query)
    log(str(len(test)) + " unit test 2 end\n")
    assert len(test) == 6
    
    log("EVALUATOR unit tests")
    query = [ ('description', 'intracranial ', []) ]
    query2 = [ ('description', 'history ', []),
    ('starttime', ['EVENT', 'starttime', 0], ['<=']),
    ('uuid', ['EVENT', 'uuid', 0], ['NOT'])
    ]
    querylist = [query, query2]
    test = evaluate(eventList, querylist, [['AND'], ['AND']], [[], []])
    log(str(len(test[0])) + " unit test 3 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 4
    
    query = [ ('description', 'intracranial ', []),
    ('description', 'hypertension ', []) ]
    query2 = [ ('description', 'intracranial ', []),
    ('starttime', ['EVENT', 'starttime', 0], ['<=']),
    ('uuid', ['EVENT', 'uuid', 0], ['NOT'])
    ]
    query3 = [ ('description', 'history ', []),
    ('starttime', ['EVENT', 'starttime', 1], ['<=']),
    ('uuid', ['EVENT', 'uuid', 1], ['NOT'])
    ]
    querylist = [query, query2, query3]
    test = evaluate(eventList, querylist, [['AND'], ['AND'], ['AND']], [[], [], []])
    log(str(len(test[0])) + " unit test 4 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 2
    
    log("TRANSLATOR unit tests")
    instr = "DESCRIPTION intracranial_hypertension AND DESCRIPTION endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 5 end " + printuuid(test[0]) + "\n")
    assert len(test[0])
    
    instr = "DESCRIPTION intracranial_hypertension NOT AND DESCRIPTION endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 6 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 0
    
    instr = "DESCRIPTION intracranial_hypertension FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 7 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 2
    
    instr = "DESCRIPTION intracranial NOT DESCRIPTION hypertension FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 8 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 0
    
    instr = "DESCRIPTION intracranial DESCRIPTION hypertension FOLLOWEDBY DESCRIPTION history ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 9 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 4
    
    instr = "DESCRIPTION intracranial DESCRIPTION hypertension FOLLOWEDBY DESCRIPTION history NOT STRICTLYBETWEEN TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 10 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 2
    
    instr = "DESCRIPTION intracranial DESCRIPTION hypertension NOT FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 11 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 1
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY DESCRIPTION history NOT PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 12 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 2
    
    log("BRACKETS unit tests")
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0)},
    {'uuid':[2], 'code': u'G93.2 ', 'endtime': datetime(2011, 5, 28, 18, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2011, 5, 28, 18, 9)},  
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2012, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2012, 5, 28, 18, 10)},   
    
    {'uuid':[5], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 18, 9)}, 
    {'uuid':[6], 'code': u'R94.5 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'abnormal results of liver function studies ', 'starttime': datetime(2014, 5, 28, 18, 9)}, 
    {'uuid':[7], 'endtime': datetime(2015, 5, 28, 20, 9), 'type': 'pathology ', 'result':15210, 'test':'ferritin', 'starttime': datetime(2015, 5, 28, 20, 9)}, 
    {'uuid':[8], 'code': u'E66.9 ', 'endtime': datetime(2015, 10, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2015, 10, 28, 18, 9)}, 
    {'uuid':[9], 'code': u'G93.2 ', 'endtime': datetime(2016, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2016, 5, 28, 18, 10)},
    {'uuid':[10], 'code': u'Z86.43 ', 'endtime': datetime(2017, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2017, 5, 28, 18, 9)}, 
    {'uuid':[11], 'endtime': datetime(2018, 5, 28, 20, 9, 1), 'type': 'admin ', 'description': 'endadmission ', 'starttime': datetime(2018, 5, 28, 20, 9, 1)},
    {'uuid':[12], 'code': u'G93.2 ', 'endtime': datetime(2019, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2019, 5, 28, 18, 10)}]
    
    instr = "DESCRIPTION intracranial NOT PRECEDEDBY DESCRIPTION history PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 13 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 1
    
    instr = "DESCRIPTION intracranial NOT FOLLOWEDBY (DESCRIPTION history) PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 14 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 1
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY (DESCRIPTION history) PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 15 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 3
    
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0), 'number': 1},
    {'uuid':[2], 'code': u'G93.2 ', 'endtime': datetime(2011, 5, 28, 18, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2011, 5, 28, 18, 9), 'number': 2},  
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2012, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2012, 5, 28, 18, 10), 'number': 3},   
    {'uuid':[5], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 18, 9), 'number': 4}, 
    {'uuid':[6], 'code': u'Z86.43 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2014, 5, 28, 18, 9), 'number': 5}, 
    {'uuid':[7], 'endtime': datetime(2015, 5, 28, 20, 9), 'type': 'pathology ', 'result':15210, 'test':'ferritin', 'starttime': datetime(2015, 5, 28, 20, 9), 'number': 6}, 
    {'uuid':[8], 'code': u'E66.9 ', 'endtime': datetime(2015, 10, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2015, 10, 28, 18, 9), 'number': 7}, 
    {'uuid':[9], 'code': u'G93.2 ', 'endtime': datetime(2016, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2016, 5, 28, 18, 10), 'number': 8},
    {'uuid':[10], 'code': u'Z86.43 ', 'endtime': datetime(2017, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2017, 5, 28, 18, 9), 'number': 9}, 
    {'uuid':[11], 'endtime': datetime(2018, 5, 28, 20, 9, 1), 'type': 'admin ', 'description': 'endadmission ', 'starttime': datetime(2018, 5, 28, 20, 9, 1), 'number': 10, 'unit': 'BLA'},
    {'uuid':[12], 'code': u'G93.2 ', 'endtime': datetime(2019, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2019, 5, 28, 18, 10), 'number': 11}
    ]
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY (DESCRIPTION history) PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test[0])) + " unit test 16 end " + printuuid(test[0]) + "\n")
    assert len(test[0]) == 3
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY (DESCRIPTION obesity FOLLOWEDBY DESCRIPTION history) PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 17 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 2
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY (DESCRIPTION obesity FOLLOWEDBY DESCRIPTION history) NOT PRECEDEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 18 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 2
    
    instr = "DESCRIPTION intracranial PRECEDEDBY (DESCRIPTION obesity FOLLOWEDBY DESCRIPTION history) NOT FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 19 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION intracranial PRECEDEDBY (DESCRIPTION history PRECEDEDBY DESCRIPTION obesity) NOT FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 20 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION intracranial PRECEDEDBY (DESCRIPTION history PRECEDEDBY (DESCRIPTION obesity)) NOT FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 21 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "intracranial PRECEDEDBY (DESCRIPTION history PRECEDEDBY (DESCRIPTION obesity)) NOT FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 22 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION intracranial NOT (DESCRIPTION history PRECEDEDBY (DESCRIPTION obesity)) NOT FOLLOWEDBY TEST ferritin ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)    
    log(str(len(test2[0])) + " unit test 23 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 0
    
    instr = "NUMERIC 10 ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 24 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "NUMERIC GREATERTHANEQUALS 10 ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 25 end " + printuuid(test2[0]) + "\n[7] is correct as its 'result' field is an integer and is 15210\n")
    assert len(test2[0]) == 3
    
    instr = "DATETIME 2014_05_28_18_09 ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 26 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DATETIME STRICTLYAFTER 2014_05_28_18_09 ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 27 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 6
    
    instr = "DESCRIPTION intracranial AND DESCRIPTION obesity STARTTIME ASPREVIOUS AFTER STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 28 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 4
    
    instr = "(DESCRIPTION intracranial) AND DESCRIPTION obesity STARTTIME ASPREVIOUS AFTER STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 29 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 4
    
    instr = "DESCRIPTION intracranial ANYNUMBEROF FOLLOWEDBY obesity ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 30 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 4
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY obesity OR FOLLOWEDBY endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 31 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 11
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY (obesity) OR FOLLOWEDBY endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 32 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 11
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY (obesity FOLLOWEDBY TEST ferritin) OR FOLLOWEDBY endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 33 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 7
    
    instr = "DESCRIPTION intracranial FOLLOWEDBY obesity OR FOLLOWEDBY TEST ferritin OR FOLLOWEDBY endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 34 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 19
    
    instr = "TYPE diagnosis DESCRIPTION intracranial FOLLOWEDBY DESCRIPTION obesity OR FOLLOWEDBY TEST ferritin OR FOLLOWEDBY endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 35 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 19
    
    instr = "DOESNOTEXIST doesnotexist OR AND DESCRIPTION startadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 36 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "(DOESNOTEXIST doesnotexist) OR AND DESCRIPTION startadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 37 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION startadmission NOT (DOESNOTEXIST doesnotexist) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 38 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "NOT (DOESNOTEXIST doesnotexist) AND DESCRIPTION startadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 39 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION intracranial GET uuid GET starttime FOLLOWEDBY obesity GET uuid OR FOLLOWEDBY TEST ferritin GET uuid ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 40 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 8
    
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0), 'number': 1},
    {'uuid':[2], 'code': u'G93.2 ', 'endtime': datetime(2011, 5, 28, 18, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2011, 5, 28, 18, 9), 'number': 2},  
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2012, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2012, 5, 28, 18, 10), 'number': 3},   
    {'uuid':[5], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 18, 9), 'number': 4}, 
    {'uuid':[6], 'code': u'Z86.43 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2014, 5, 28, 18, 9), 'number': 5}, 
    {'uuid':[7], 'endtime': datetime(2015, 5, 28, 20, 9), 'type': 'pathology ', 'result':15210, 'test':'ferritin', 'starttime': datetime(2015, 5, 28, 20, 9), 'number': 6}, 
    {'uuid':[8], 'code': u'E66.9 ', 'endtime': datetime(2015, 10, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2015, 10, 28, 18, 9), 'number': 7}, 
    {'uuid':[9], 'code': u'G93.2 ', 'endtime': datetime(2016, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2016, 5, 28, 18, 10), 'number': 8},
    {'uuid':[10], 'code': u'Z86.43 ', 'endtime': datetime(2017, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2017, 5, 28, 18, 9), 'number': 9}, 
    {'uuid':[11], 'endtime': datetime(2018, 5, 28, 20, 9, 1), 'type': 'admin ', 'description': 'endadmission ', 'starttime': datetime(2018, 5, 28, 20, 9, 1), 'number': 10, 'unit': 'BLA'},
    {'uuid':[12], 'code': u'G93.2 ', 'endtime': datetime(2019, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2019, 5, 28, 18, 10), 'number': 11}
    ]
    
    instr = "DESCRIPTION intracranial GET uuid FOLLOWEDBY (obesity FOLLOWEDBY TEST ferritin GET uuid) OR FOLLOWEDBY endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 41 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 7
    
    instr = "(DESCRIPTION intracranial GET uuid) AND DESCRIPTION obesity STARTTIME ASPREVIOUS AFTER STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 42 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 4
    
    instr = "(DESCRIPTION intracranial GET uuid) OR AND DESCRIPTION startadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 43 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 9
    
    instr = "(DESCRIPTION intracranial GET uuid) FOLLOWEDBY DESCRIPTION startadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 44 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 0
    
    instr = "(DESCRIPTION intracranial GET uuid) PRECEDEDBY DESCRIPTION endadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 45 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION startadmission GET uuid FOLLOWEDBY DESCRIPTION endadmission GET uuid NOT STRICTLYBETWEEN DESCRIPTION startadmission NOT STRICTLYBETWEEN endadmission STRICTLYBETWEEN DESCRIPTION obesity GET uuid ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 46 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 2
    
    instr = "DESCRIPTION startadmission GET uuid FOLLOWEDBY DESCRIPTION endadmission GET uuid NOT STRICTLYBETWEEN DESCRIPTION startadmission NOT STRICTLYBETWEEN endadmission STRICTLYBETWEEN (DESCRIPTION obesity GET uuid OR AND DESCRIPTION hypertension GET uuid) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 47 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 11
    
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0), 'number': 1},
    {'uuid':[2], 'code': u'G93.2 ', 'endtime': datetime(2011, 5, 28, 18, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2011, 5, 28, 18, 9), 'number': 2},  
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2012, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2012, 5, 28, 18, 10), 'number': 3},   
    {'uuid':[5], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 18, 9), 'number': 4}, 
    {'uuid':[6], 'code': u'Z86.43 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2014, 5, 28, 18, 9), 'number': 5}, 
    {'uuid':[7], 'endtime': datetime(2015, 5, 28, 20, 9), 'type': 'pathology ', 'result':15210, 'test':'ferritin', 'starttime': datetime(2015, 5, 28, 20, 9), 'number': 6}, 
    {'uuid':[8], 'code': u'E66.9 ', 'endtime': datetime(2015, 10, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2015, 10, 28, 18, 9), 'number': 7}, 
    {'uuid':[9], 'code': u'G93.2 ', 'endtime': datetime(2016, 5, 28, 18, 10),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2016, 5, 28, 18, 10), 'number': 8},
    {'uuid':[10], 'code': u'Z86.43 ', 'endtime': datetime(2017, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2017, 5, 28, 18, 9), 'number': 9}, 
    {'uuid':[11], 'endtime': datetime(2018, 5, 28, 20, 9, 1), 'type': 'admin ', 'description': 'endadmission ', 'starttime': datetime(2018, 5, 28, 20, 9, 1), 'number': 10, 'unit': 'BLA'},
    {'uuid':[13], 'endtime': datetime(2019, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2019, 5, 26, 10, 0), 'number': 1},
    {'uuid':[14], 'code': u'E66.9 ', 'endtime': datetime(2019, 10, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2019, 10, 28, 18, 9), 'number': 7}, 
    {u'uuid': [17], u'result': 113.0, u'starttime': datetime(2019, 10, 28, 18, 9), u'test': u'sodium ', u'endtime': datetime(2019, 10, 28, 18, 9), u'type': u'pathology ', u'uom': u'mmol/litre '},
    {'uuid':[15], 'code': u'G93.2 ', 'endtime': datetime(2019, 10, 28, 18, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2019, 10, 28, 18, 9), 'number': 8},
    {'uuid':[16], 'endtime': datetime(2019, 11, 28, 20, 9, 1), 'type': 'admin ', 'description': 'endadmission ', 'starttime': datetime(2019, 11, 28, 20, 9, 1), 'number': 10, 'unit': 'BLA'}
    ]
    
    instr = "DESCRIPTION intracranial ONEOF AND DESCRIPTION startadmission ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 48 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 6
    
    #debug = True
    #debug2 = True
    instr = "DESCRIPTION startadmission GET uuid FOLLOWEDBY DESCRIPTION endadmission GET uuid NOT STRICTLYBETWEEN DESCRIPTION startadmission NOT STRICTLYBETWEEN DESCRIPTION endadmission STRICTLYBETWEEN (DESCRIPTION obesity GET uuid ONEOF AND DESCRIPTION hypertension GET uuid) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 49 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 7
    
    instr = "DESCRIPTION startadmission GET uuid FOLLOWEDBY DESCRIPTION endadmission GET uuid NOT STRICTLYBETWEEN DESCRIPTION startadmission NOT STRICTLYBETWEEN DESCRIPTION endadmission STRICTLYBETWEEN (DESCRIPTION obesity GET uuid AND DESCRIPTION hypertension GET uuid) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log("GET: ")
    for i in test2[2]:
        log(i)
    log(str(len(test2[0])) + " unit test 50 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 7
    
    instr = "DESCRIPTION intracranial AND DESCRIPTION obesity STARTTIME ASPREVIOUS BEFORE OFFSETT-01 STARTTIME STARTTIME ASPREVIOUS AFTER OFFSETT+01 STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 51 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 0
    
    instr = "(DESCRIPTION intracranial) AND DESCRIPTION obesity STARTTIME ASPREVIOUS BEFORE OFFSETT-01 STARTTIME STARTTIME ASPREVIOUS AFTER OFFSETT+01 STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 52 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 0
    
    instr = "DESCRIPTION intracranial AND DESCRIPTION obesity STARTTIME ASPREVIOUS BEFORE OFFSETT+01 STARTTIME STARTTIME ASPREVIOUS AFTER OFFSETT-01 STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 53 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 1
    
    instr = "DESCRIPTION intracranial AND DESCRIPTION obesity STARTTIME ASPREVIOUS BEFORE OFFSETT+750_00_00 STARTTIME STARTTIME ASPREVIOUS AFTER OFFSETT-0000_00_00 STARTTIME ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 54 end " + printuuid(test2[0]) + "\n")
    assert len(test2[0]) == 3
    
    #debug3 = True
    import output
    outchop = chopeventlist(output.testchop)
    
    log("start chopped list")
    stime = datetime.now()
    log(stime)
    instr = "DESCRIPTION hypertension GET uuid ENDSEARCH"
    test, connectors, gets = translate(instr)
    results = []
    for oc in outchop:
        test2 = evaluate(oc, test, connectors, gets)
        if not (test2[0] == []):
            results.append(test2[2])
    etime = datetime.now()
    log(instr)
    log(str(len(results)) + " unit test 55 end")
    log("chopped list done")
    log(etime)
    log("time taken: " + str(etime - stime))
    assert len(results) == 25
    log("")
    
    log("start SAMEADMISSION test")
    stime = datetime.now()
    log(stime)
    instr = "(SAMEADMISSION DESCRIPTION hypertension GET uuid) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(output.testchop, test, connectors, gets)
    etime = datetime.now()
    log(instr)
    log(str(len(test2[0])) + " unit test 56 end " + printuuid(test2[0]))
    log(etime)
    log("time taken: " + str(etime - stime))
    assert len(test2[0]) == 26
    log("")
    
    #debug = True
    #debug2 = True
    stime = datetime.now()
    log(stime)
    instr = "DOESNOTEXIST doesnotexist OR (SAMEADMISSION DESCRIPTION hypertension GET uuid) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(output.testchop, test, connectors, gets)
    etime = datetime.now()
    log(instr)
    log(str(len(test2[0])) + " unit test 57 end " + printuuid(test2[0]))
    log(etime)
    log("time taken: " + str(etime - stime))
    assert len(test2[0]) == 26
    log("")
    
    stime = datetime.now()
    log(stime)
    instr = "(SAMEADMISSION DESCRIPTION infection FOLLOWEDBY isolation) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(output.testchop, test, connectors, gets)
    etime = datetime.now()
    log(instr)
    log(str(len(test2[0])) + " unit test 58 end " + printuuid(test2[0]))
    log(etime)
    log("time taken: " + str(etime - stime))
    assert len(test2[0]) == 4
    log("")
    
    instr = "DESCRIPTION startadmission GET uuid FOLLOWEDBY DESCRIPTION endadmission GET uuid NOT STRICTLYBETWEEN DESCRIPTION startadmission NOT STRICTLYBETWEEN DESCRIPTION endadmission STRICTLYBETWEEN (TYPE diagnosis GET description AND TYPE pathology TEST Sodium RESULT NUMERIC GREATERTHANEQUALS 0.000000 RESULT NUMERIC LESSTHANEQUALS 120.000000 GET result) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 59 end " + printuuid(test2[0]))
    assert len(test2[0]) == 2
    log("")
    
    instr = "(SAMEADMISSION TYPE diagnosis GET description AND TYPE pathology TEST Sodium RESULT NUMERIC GREATERTHANEQUALS 0.000000 RESULT NUMERIC LESSTHANEQUALS 120.000000 GET result) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 60 end " + printuuid(test2[0]))
    assert len(test2[0]) == 2
    log("")
    
    instr = "(SAMEADMISSION doesnotexist ANYNUMBEROF OR AND TYPE diagnosis GET description AND TYPE pathology TEST Sodium RESULT NUMERIC GREATERTHANEQUALS 0.000000 RESULT NUMERIC LESSTHANEQUALS 120.000000 GET result) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 61 end " + printuuid(test2[0]))
    assert len(test2[0]) == 1
    log("")
    
    instr = "(obesity OR AND ferritin) FOLLOWEDBY tobacco ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 62 end " + printuuid(test2[0]))
    assert len(test2[0]) == 6
    log("")
    
    #brackets beginning another bracket
    instr = "(SAMEADMISSION (obesity OR AND ferritin) FOLLOWEDBY tobacco) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 62 end " + printuuid(test2[0]))
    assert len(test2[0]) == 6
    log("")
    
    #GET return None
    instr = "(SAMEADMISSION (obesity GET doesnotexist OR AND ferritin GET doesnotexist) FOLLOWEDBY tobacco GET doesnotexist) ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 63 end " + printuuid(test2[0]))
    assert len(test2[0]) == 6
    print(test2[2])
    log("")
    
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0), 'number': 1},
    {'uuid':[2], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 18, 9), 'number': 4}, 
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2013, 5, 28, 19, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2013, 5, 28, 19, 9), 'number': 2},   #same time as 2
    {'uuid':[4], 'code': u'G93.2 ', 'endtime': datetime(2013, 5, 28, 19, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2013, 5, 28, 19, 9), 'number': 3},   #1 day later
    {'uuid':[5], 'code': u'Z86.43 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2014, 5, 28, 18, 9), 'number': 5}, 
    ]
    
    #NOT STRICTLYBETWEEN strictness testing
    instr = "obesity FOLLOWEDBY intracranial NOT STRICTLYBETWEEN intracranial ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 64 end " + printuuid(test2[0]))
    assert len(test2[0]) == 2
    print(test2[2])
    log("")
    
    
    #PRECEDEDBY and BETWEEN TESTING
    eventList = [{'uuid':[1], 'endtime': datetime(2010, 5, 26, 10, 0), 'type': 'admin ', 'description': 'startadmission ', 'starttime': datetime(2010, 5, 26, 10, 0), 'number': 1},
    {'uuid':[2], 'code': u'E66.9 ', 'endtime': datetime(2013, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'obesity, unspecified ', 'starttime': datetime(2013, 5, 28, 19, 9), 'number': 4}, 
    {'uuid':[3], 'code': u'G93.2 ', 'endtime': datetime(2013, 5, 28, 19, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2013, 5, 28, 20, 9), 'number': 2},   #same time as 2
    {'uuid':[4], 'code': u'G93.2 ', 'endtime': datetime(2013, 5, 28, 19, 9),'type': 'diagnosis ', 'description': u'benign intracranial hypertension ', 'starttime': datetime(2013, 5, 28, 21, 9), 'number': 3},   #1 day later
    {'uuid':[5], 'code': u'Z86.43 ', 'endtime': datetime(2014, 5, 28, 18, 9), 'type': 'diagnosis ', 'description': u'personal history of tobacco use disorder ', 'starttime': datetime(2014, 5, 28, 22, 9), 'number': 5}, 
    ]
    
    instr = "obesity FOLLOWEDBY intracranial NOT BETWEEN intracranial ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 65 end " + printuuid(test2[0]))
    assert len(test2[0]) == 1
    print(test2[2])
    log("")
    
    #debug = True
    #debug2 = True
    instr = "intracranial PRECEDEDBY obesity NOT BETWEEN intracranial ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 66 end " + printuuid(test2[0]))
    assert len(test2[0]) == 1
    print(test2[2])
    log("")
    
    instr = "intracranial AND obesity ONEOF AND intracranial NOT UUID ASPREVIOUS UUID ENDSEARCH"
    test, connectors, gets = translate(instr)
    test2 = evaluate(eventList, test, connectors, gets)
    log(instr)
    log(str(len(test2[0])) + " unit test 67 end " + printuuid(test2[0]))
    assert len(test2[0]) == 4
    print(test2[2])
    log("")
    
    
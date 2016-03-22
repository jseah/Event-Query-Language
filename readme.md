# Event Query Language
Event Query Language is a search language for ordered datasets.  Event Query Language allows you to search such datasets for relationships between events.  

Event Query Language implements this by allowing relative search terms between events.  Eg:

* Find all events with a Description containing 'dog' and events with a Description containing 'cat' that have a Starttime after the previous event
* Find all events with a Description containing 'cat' and find all events with a Description containing 'dog' that have the same Count as the previous event

Such linked events are returned as entire sequences that fulfill the search criteria.  

Eventlist:
```[{EventID: 1, Description: cat, starttime: 12am, count: 5},
{EventID: 2, Description: cat, starttime: 3pm, count: 1},
{EventID: 3, Description: dog, starttime: 9am, count: 5},
{EventID: 4, Description: dog, starttime: 6pm, count: 1}]
```

The EventIDs of the events that the 1st search returns:
* [1, 3]
* [2, 3]

The EventIDs of the events that the 2nd search returns:
* [1, 3]
* [2, 4]

## Install
Download eventsearch.py and place it in your working directory, simply import eventsearch to access the methods
output.py is required for the testing script only

## Examples
To use Event Query Language, you must format your events as a dictionary:

```{Descriptor: Value, Descriptor: Value}
```
Dates must be stored as python's datetime.datetime format.  String values are not case sensitive. 

Events are then packaged into a list of events to form an eventlist.  

The two main functions of Event Query Language are the methods Evaluate and Translate.  

Evaluate takes an eventlist and three synchronized lists called queries, connectors and gets.  
Translate implements a simple syntax to turn a human readable string into the lists of queries, connectors and gets that Evaluate requires.  
Translate and Evaluate operate independently.  

Translate separates words by spacebar and uses ALLCAPS to find keywords, underscores are turned into spacebars after the words have been split.  Here are a few examples of a string that Translate parses:

This searchstring finds all possible combinations of events with description "intracranial hypertension" and events with a description "endadmission".  ALLCAPS keywords that are not reserved by Translate are used to find a descriptor in your events.  
```DESCRIPTION intracranial_hypertension 
AND DESCRIPTION endadmission 
ENDSEARCH
```

Relationships between events use the ASPREVIOUS keyword, this refers to the event directly previous to this event by default (the same as ASPREVIOUS-1). 
```DESCRIPTION intracranial 
NOT AND DESCRIPTION intracranial 
    COUNT ASPREVIOUS GREATERTHAN COUNT 
ENDSEARCH
```

Special followedby and precededby keywords allow easy linking using a starttime descriptor; without having to explicitly write out the relationships. 
```DESCRIPTION intracranial 
FOLLOWEDBY DESCRIPTION obesity  
ENDSEARCH
```
Compared with:
```DESCRIPTION intracranial 
AND DESCRIPTION obesity  
    STARTTIME ASPREVIOUS AFTER STARTTIME 
    NOT UUID ASPREVIOUS UUID 
ENDSEARCH
```

Searches can be nested inside brackets, criteria applied to the bracket will apply to all events returned from inside the bracket. 
```DESCRIPTION intracranial
FOLLOWEDBY (
    DESCRIPTION obesity 
    FOLLOWEDBY TEST ferritin
) 
OR FOLLOWEDBY DESCRIPTION endadmission 
ENDSEARCH
```